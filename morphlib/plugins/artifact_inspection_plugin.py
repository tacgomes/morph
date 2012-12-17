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

import morphlib

from morphlib.bins import call_in_artifact_directory
from morphlib.extractedtarball import ExtractedTarball
from morphlib.mountableimage import MountableImage


class NotASystemArtifactError(cliapp.AppException):

    def __init__(self, artifact):
        cliapp.AppException.__init__(
                self, '%s is not a system artifact' % artifact)


class ManifestGenerator(object):

    def __init__(self, app):
        self.app = app

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
        
            artifacts.append({
                'cache-key': metadata['cache-key'],
                'name': metadata['artifact-name'],
                'kind': metadata['kind'],
                'sha1': metadata['sha1'],
                'original_ref': metadata['original_ref'],
                'repo': metadata['repo'],
                'morphology': metadata['morphology']
            })
        
        # Generate a format string for dumping the information.
        fmt = self._generate_output_format(artifacts)
        
        # Print information about system, strata and chunks.
        self._print_artifacts(fmt, artifacts, 'system')
        self._print_artifacts(fmt, artifacts, 'stratum')
        self._print_artifacts(fmt, artifacts, 'chunk')

    def _generate_output_format(self, artifacts):
        colwidths = {}
        for artifact in artifacts:
            for key, value in artifact.iteritems():
                colwidths[key] = max(colwidths.get(key, 0), len(value))

        colwidths['first'] = sum([colwidths['cache-key'],
                                  colwidths['kind'],
                                  colwidths['name']]) + 1

        return 'artifact=%%-%is\t' \
               'version=%%-%is\t' \
               'commit=%%-%is\t' \
               'repository=%%-%is\t' \
               'ref=%%-%is\t' \
               'morphology=%%-%is\n' % (
                len('artifact=') + colwidths['first'],
                len('version=') + colwidths['version'],
                len('commit=') + colwidths['sha1'],
                len('repository=') + colwidths['repo'],
                len('ref=') + colwidths['original_ref'],
                len('morphology=') + colwidths['morphology'])

    def _print_artifacts(self, fmt, artifacts, kind):
        for artifact in sorted(artifacts, key=lambda x: x['name']):
            if artifact['kind'] == kind:
                self.app.output.write(fmt % (
                    '%s.%s.%s' % (artifact['cache-key'],
                                  artifact['kind'],
                                  artifact['name']),
                    artifact['version'],
                    artifact['sha1'],
                    artifact['repo'],
                    artifact['original_ref'],
                    artifact['morphology']))


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
        '''Run a command inside an extracted/mounted chunk or system.'''

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
