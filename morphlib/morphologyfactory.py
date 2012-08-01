# Copyright (C) 2012  Codethink Limited
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

import morphlib
import cliapp


class MorphologyFactoryError(cliapp.AppException):
    pass


class AutodetectError(MorphologyFactoryError):
    def __init__(self, repo_name, ref):
        MorphologyFactoryError.__init__(
            self, "Failed to determine the build system of repo %s at "
                  "ref %s" % (repo_name, ref))


class NotcachedError(MorphologyFactoryError):
    def __init__(self, repo_name):
        MorphologyFactoryError.__init__(
            self, "Repository %s is not cached locally and there is no "
                  "remote cache specified" % repo_name)


class MorphologyFactory(object):

    '''An way of creating morphologies which will provide a default'''

    def __init__(self, local_repo_cache, remote_repo_cache=None):
        self._lrc = local_repo_cache
        self._rrc = remote_repo_cache

    def get_morphology(self, reponame, sha1, filename):
        try:
            text = self._cat_text(reponame, sha1, filename)
        except:
            text = self._autodetect_text(reponame, sha1, filename)

        try:
            morphology = morphlib.morph2.Morphology(text)
        except ValueError as e:
            raise morphlib.Error("Error parsing %s: %s" %
                                 (filename, e.message))

        method_name = '_check_and_tweak_%s' % morphology['kind']
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            method(morphology, reponame, sha1, filename)

        return morphology

    def _cat_text(self, reponame, sha1, filename):
        if self._lrc.has_repo(reponame):
            repo = self._lrc.get_repo(reponame)
            return repo.cat(sha1, filename)
        elif self._rrc is not None:
            return self._rrc.cat_file(reponame, sha1, filename)
        else:
            raise NotcachedError(reponame)

    def _autodetect_text(self, reponame, sha1, filename):
        # TODO get lists of files from the cache to reduce round trips
        if self._lrc.has_repo(reponame):
            repo = self._lrc.get_repo(reponame)

            def has_file(filename):
                try:
                    repo.cat(sha1, filename)
                    return True
                except IOError:
                    return False
        elif self._rrc is not None:
            def has_file(filename):
                try:
                    text = self._rrc.cat_file(reponame, sha1, filename)
                    return True
                except morphlib.remoterepocache.CatFileError:
                    return False
        else:
            raise NotcachedError(reponame)
        bs = morphlib.buildsystem.detect_build_system(has_file)
        if bs is None:
            raise AutodetectError(reponame, sha1)
        # TODO consider changing how morphs are located to be by morph
        #      name rather than filename, it would save creating a
        #      filename only to strip it back to its morph name again
        #      and would allow future changes like morphologies being
        #      stored as git metadata instead of as a file in the repo
        assert filename.endswith('.morph')
        morph_name = filename[:-len('.morph')]
        morph_text = bs.get_morphology_text(morph_name)
        return morph_text

    def _check_and_tweak_system(self, morphology, reponame, sha1, filename):
        '''Check and tweak a system morphology.'''

        if morphology['arch'] is None:  # pragma: no cover
            raise morphlib.Error('No arch specified in system %s '
                                 '(arch is a mandatory field)' %
                                 filename)

        if not morphology['system-kind']:
            raise morphlib.Error('No system-kind defined in system %s '
                                 '(it is a mandatory field)' % filename)

        name = morphology['name']
        if morphology['arch'] == 'arm':
            morphology.builds_artifacts = [name + '-kernel', name + '-rootfs']
        else:
            # FIXME: -rootfs is a misnomer, should be -disk, but can't
            # change this during refactoring.
            morphology.builds_artifacts = [name + '-rootfs']

        morphology.needs_staging_area = False
        morphology.needs_artifact_metadata_cached = False

    def _check_and_tweak_stratum(self, morphology, reponame, sha1, filename):
        '''Check and tweak a stratum morphology.'''

        for source in morphology['sources']:  # pragma: no cover
            if source.get('build-depends', None) is None:
                name = source.get('name', source.get('repo', 'unknown'))
                raise morphlib.Error('No build dependencies '
                                     'stratum %s for chunk %s '
                                     '(build-depends is a mandatory '
                                     'field)' %
                                     (filename, name))

        morphology.builds_artifacts = [morphology['name']]
        morphology.needs_staging_area = False
        morphology.needs_artifact_metadata_cached = True

    def _check_and_tweak_chunk(self, morphology, reponame, sha1, filename):
        '''Check and tweak a chunk morphology.'''

        if 'chunks' in morphology and len(morphology['chunks']) > 1:
            morphology.builds_artifacts = morphology['chunks'].keys()
        else:
            morphology.builds_artifacts = [morphology['name']]

        morphology.needs_staging_area = True
        morphology.needs_artifact_metadata_cached = False
