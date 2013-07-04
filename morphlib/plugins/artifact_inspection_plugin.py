# Copyright (C) 2012-2013  Codethink Limited
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


import cliapp
import glob
import json
import os
import re

import morphlib

from morphlib.bins import call_in_artifact_directory
from morphlib.extractedtarball import ExtractedTarball
from morphlib.mountableimage import MountableImage


class NotASystemArtifactError(cliapp.AppException):

    def __init__(self, artifact):
        cliapp.AppException.__init__(
                self, '%s is not a system artifact' % artifact)


class ProjectVersionGuesser(object):

    def __init__(self, app, lrc, rrc, interesting_files):
        self.app = app
        self.lrc = lrc
        self.rrc = rrc
        self.interesting_files = interesting_files

    def file_contents(self, repo, ref, tree):
        filenames = [x for x in self.interesting_files if x in tree]
        if filenames:
            if self.lrc.has_repo(repo):
                repository = self.lrc.get_repo(repo)
                for filename in filenames:
                    yield filename, repository.cat(ref, filename)
            elif self.rrc:
                for filename in filenames:
                    yield filename, self.rrc.cat_file(repo, ref, filename)


class AutotoolsVersionGuesser(ProjectVersionGuesser):

    def __init__(self, app, lrc, rrc):
        ProjectVersionGuesser.__init__(self, app, lrc, rrc, [
            'configure.ac',
            'configure.in',
            'configure.ac.in',
            'configure.in.in',
        ])

    def guess_version(self, repo, ref, tree):
        version = None
        for filename, data in self.file_contents(repo, ref, tree):
            # First, try to grep for AC_INIT()
            version = self._check_ac_init(data)
            if version:
                self.app.status(
                        msg='%(repo)s: Version of %(ref)s detected '
                            'via %(filename)s:AC_INIT: %(version)s',
                        repo=repo, ref=ref, filename=filename,
                        version=version, chatty=True)
                break

            # Then, try running autoconf against the configure script
            version = self._check_autoconf_package_version(filename, data)
            if version:
                self.app.status(
                        msg='%(repo)s: Version of %(ref)s detected '
                            'by processing %(filename)s: %(version)s',
                        repo=repo, ref=ref, filename=filename,
                        version=version, chatty=True)
                break
        return version

    def _check_ac_init(self, data):
        data = data.replace('\n', ' ')
        for macro in ['AC_INIT', 'AM_INIT_AUTOMAKE']:
            pattern = r'.*%s\((.*?)\).*' % macro
            if not re.match(pattern, data):
                continue
            acinit = re.sub(pattern, r'\1', data)
            if acinit:
                version = acinit.split(',')
                if macro == 'AM_INIT_AUTOMAKE' and len(version) == 1:
                    continue
                version = version[0] if len(version) == 1 else version[1]
                version = re.sub('[\[\]]', '', version).strip()
                version = version.split()[0]
                if version:
                    if version and version[0].isdigit():
                        return version
        return None

    def _check_autoconf_package_version(self, filename, data):
        tempdir = morphlib.tempdir.Tempdir(self.app.settings['tempdir'])
        with open(tempdir.join(filename), 'w') as f:
            f.write(data)
        exit_code, output, errors = self.app.runcmd_unchecked(
                ['autoconf', filename],
                ['grep', '^PACKAGE_VERSION='],
                ['cut', '-d=', '-f2'],
                ['sed', "s/'//g"],
                cwd=tempdir.dirname)
        tempdir.remove()
        version = None
        if output:
            output = output.strip()
            if output and output[0].isdigit():
                version = output
        if exit_code != 0:
            self.app.status(
                    msg='%(repo)s: Failed to detect version from '
                        '%(ref)s:%(filename)s',
                    repo=repo, ref=ref, filename=filename, chatty=True)
        return version


class VersionGuesser(object):

    def __init__(self, app):
        self.app = app
        self.lrc, self.rrc = morphlib.util.new_repo_caches(app)
        self.guessers = [
            AutotoolsVersionGuesser(app, self.lrc, self.rrc)
        ]

    def guess_version(self, repo, ref):
        self.app.status(msg='%(repo)s: Guessing version of %(ref)s',
                        repo=repo, ref=ref, chatty=True)
        version = None
        try:
            if self.lrc.has_repo(repo):
                repository = self.lrc.get_repo(repo)
                if not self.app.settings['no-git-update']:
                    repository.update()
                tree = repository.ls_tree(ref)
            elif self.rrc:
                repository = None
                tree = self.rrc.ls_tree(repo, ref)
            else:
                return None
            for guesser in self.guessers:
                version = guesser.guess_version(repo, ref, tree)
                if version:
                    break
        except cliapp.AppException, err:
            self.app.status(msg='%(repo)s: Failed to list files in %(ref)s',
                            repo=repo, ref=ref, chatty=True)
        return version


class ManifestGenerator(object):

    def __init__(self, app):
        self.app = app
        self.version_guesser = VersionGuesser(app)

    def generate(self, artifact, dirname):
        # Try to find a directory with baserock metadata files.
        metadirs = [
            os.path.join(dirname, 'factory', 'baserock'),
            os.path.join(dirname, 'baserock')
        ]
        existing_metadirs = [x for x in metadirs if os.path.isdir(x)]
        if not existing_metadirs:
            raise NotASystemArtifactError(artifact)
        metadir = existing_metadirs[0]

        # Collect all meta information about the system, its strata
        # and its chunks that we are interested in.
        artifacts = []
        for basename in glob.glob(os.path.join(metadir, '*.meta')):
            metafile = os.path.join(metadir, basename)
            metadata = json.load(open(metafile))

            # Try to guess the version of this artifact
            version = self.version_guesser.guess_version(
                    metadata['repo'], metadata['sha1'])
            if version is None:
                version = ''
            else:
                version = '-%s' % version

            fst_col = '%s.%s.%s%s' % (metadata['cache-key'][:7],
                                      metadata['kind'],
                                      metadata['artifact-name'],
                                      version)

            original_ref = metadata['original_ref']
            if metadata['kind'] in ('system', 'stratum'):
                original_ref = original_ref[: len('baserock/builds/') + 7]

            artifacts.append({
                'kind': metadata['kind'],
                'name': metadata['artifact-name'],
                'fst_col': fst_col,
                'repo': metadata['repo'],
                'original_ref': original_ref,
                'sha1': metadata['sha1'][:7]
            })
        
        # Generate a format string for dumping the information.
        fmt = self._generate_output_format(artifacts)
        self.app.output.write(fmt % ('ARTIFACT', 'REPOSITORY',
                                     'REF', 'COMMIT'))

        # Print information about system, strata and chunks.
        self._print_artifacts(fmt, artifacts, 'system')
        self._print_artifacts(fmt, artifacts, 'stratum')
        self._print_artifacts(fmt, artifacts, 'chunk')

    def _generate_output_format(self, artifacts):
        colwidths = {}
        for artifact in artifacts:
            for key, value in artifact.iteritems():
                colwidths[key] = max(colwidths.get(key, 0), len(value))

        return '%%-%is\t' \
               '%%-%is\t' \
               '%%-%is\t' \
               '%%-%is\n' % (
                colwidths['fst_col'],
                colwidths['repo'],
                colwidths['original_ref'],
                colwidths['sha1'])

    def _print_artifacts(self, fmt, artifacts, kind):
        for artifact in sorted(artifacts, key=lambda x: x['name']):
            if artifact['kind'] == kind:
                self.app.output.write(fmt % (artifact['fst_col'],
                                             artifact['repo'],
                                             artifact['original_ref'],
                                             artifact['sha1']))


class ArtifactInspectionPlugin(cliapp.Plugin):

    def enable(self):
        self.app.add_subcommand('run-in-artifact',
                                self.run_in_artifact,
                                arg_synopsis='ARTIFACT CMD')
        self.app.add_subcommand('generate-manifest',
                                self.generate_manifest,
                                arg_synopsis='ROOTFS_ARTIFACT')

    def disable(self):
        pass

    def run_in_artifact(self, args):
        '''Run a command inside an extracted/mounted chunk or system.

        Command line arguments:

        * `ARTIFACT` is a filename for the artifact.
        * `CMD` is the command to run.

        run-in-artifact unpacks an artifact, and runs a command in
        the temporary directory it was unpacked to.

        The command must be given to Morph as a single argument, so
        use shell quoting appropriately.

        '''

        if len(args) < 2:
            raise cliapp.AppException(
                    'run-in-artifact requires arguments: a chunk or '
                    'system artifact and a a shell command')

        artifact, cmd = args[0], args[1:]

        def run_command_in_dir(dirname):
            output = self.app.runcmd(cmd, cwd=dirname)
            self.app.output.write(output)

        call_in_artifact_directory(self.app, artifact, run_command_in_dir)

    def generate_manifest(self, args):
        '''Generate a content manifest for a system image.'''

        if len(args) != 1:
            raise cliapp.AppException('morph generate-manifest expects '
                                      'a system image as its input')

        artifact = args[0]

        def generate_manifest(dirname):
            generator = ManifestGenerator(self.app)
            generator.generate(artifact, dirname)

        call_in_artifact_directory(self.app, artifact, generate_manifest)
