# Copyright (C) 2015  Codethink Limited
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
# with this program.  If not, see <http://www.gnu.org/licenses/>.


import os
import shutil
import tempfile
import unittest

import morphlib
from morphlib.sourceresolver import (SourceResolver,
                                     PickleCacheManager,
                                     MorphologyNotFoundError)
from morphlib.remoterepocache import CatFileError, LsTreeError


class FakeRemoteRepoCache(object):

    def cat_file(self, reponame, sha1, filename):
        if filename.endswith('.morph'):
            return '''{
                 "name": "%s",
                 "kind": "chunk",
                 "build-system": "dummy"
             }''' % filename[:-len('.morph')]
        return 'text'

    def ls_tree(self, reponame, sha1):
        return []


class FakeLocalRepo(object):

    morphologies = {
        'chunk.morph': '''
                name: chunk
                kind: chunk
                build-system: dummy
            ''',
        'chunk-split.morph': '''
                name: chunk-split
                kind: chunk
                build-system: dummy
                products:
                    - artifact: chunk-split-runtime
                      include: []
                    - artifact: chunk-split-devel
                      include: []
            ''',
        'stratum.morph': '''
                name: stratum
                kind: stratum
                chunks:
                    - name: chunk
                      repo: test:repo
                      ref: sha1
                      build-mode: bootstrap
                      build-depends: []
            ''',
        'stratum-no-bdeps-no-bootstrap.morph': '''
                name: stratum-no-bdeps-no-bootstrap
                kind: stratum
                chunks:
                    - name: chunk
                      repo: test:repo
                      ref: sha1
                      build-depends: []
            ''',
        'stratum-bdeps-no-bootstrap.morph': '''
                name: stratum-bdeps-no-bootstrap
                kind: stratum
                build-depends:
                    - morph: stratum
                chunks:
                    - name: chunk
                      repo: test:repo
                      ref: sha1
                      build-depends: []
            ''',
        'stratum-empty.morph': '''
                name: stratum-empty
                kind: stratum
            ''',
        'system.morph': '''
                name: system
                kind: system
                arch: %(arch)s
                strata:
                    - morph: stratum
            ''',
        'parse-error.morph': ''' name''',
        'name-mismatch.morph': '''
                name: fred
                kind: stratum
            ''',
    }

    def __init__(self):
        self.arch = 'x86_64'

    def read_file(self, filename, ref):
        if filename in self.morphologies:
            values = {
                'arch': self.arch,
            }
            return self.morphologies[filename] % values
        elif filename.endswith('.morph'):
            return '''name: %s
                kind: chunk
                build-system: dummy''' % filename[:-len('.morph')]
        return 'text'

    def list_files(self, ref, recurse):
        return self.morphologies.keys()

    def update(self):
        pass


class FakeLocalRepoCache(object):

    def __init__(self, lr):
        self.lr = lr

    def has_repo(self, reponame):
        return True

    def get_repo(self, reponame):
        return self.lr

    def cache_repo(self, reponame):
        return self.lr

    def get_updated_repo(self, reponame, ref=None):
        return self.lr


class SourceResolverTests(unittest.TestCase):

    def setUp(self):
        # create temp "definitions" repo
        # set self.sr._definitions_repo to that
        # trick it into presenting temp repo using FakeLocalRepoCache
        # magic
        self.lr = FakeLocalRepo()
        self.lrc = FakeLocalRepoCache(self.lr)
        self.rrc = FakeRemoteRepoCache()

        self.cachedir = tempfile.mkdtemp()
        buildsystem_cache_file = os.path.join(self.cachedir,
            'detected-chunk-buildsystems.cache.pickle')
        buildsystem_cache_manager = PickleCacheManager(
            buildsystem_cache_file, 1000)

        tree_cache_file = os.path.join(self.cachedir, 'trees.cache.pickle')
        tree_cache_manager = PickleCacheManager(tree_cache_file, 1000)

        def status(msg='', **kwargs):
            pass

        self.sr = SourceResolver(self.lrc, self.rrc, tree_cache_manager,
                                 buildsystem_cache_manager, True, status)
        self.lsr = SourceResolver(self.lrc, None, tree_cache_manager,
                                  buildsystem_cache_manager, True, status)

    def tearDown(self):
        shutil.rmtree(self.cachedir)

    def nolocalfile(self, *args):
        raise IOError('File not found')

    def noremotefile(self, *args):
        raise CatFileError('reponame', 'ref', 'filename')

    def noremoterepo(self, *args):
        raise LsTreeError('reponame', 'ref')

    def localmorph(self, *args):
        return ['chunk.morph']

    def nolocalmorph(self, *args):
        if args[0].endswith('.morph'):
            raise IOError('File not found')
        return 'text'

    def autotoolsbuildsystem(self, *args, **kwargs):
        return ['configure.in']

    def emptytree(self, *args, **kwargs):
        return []

    def remotemorph(self, *args, **kwargs):
        return ['remote-chunk.morph']

    def noremotemorph(self, *args):
        if args[-1].endswith('.morph'):
            raise CatFileError('reponame', 'ref', 'filename')
        return 'text'

    def doesnothaverepo(self, reponame):
        return False

    def test_gets_morph_from_local_repo(self):
        self.lr.list_files = self.localmorph
        morph = self.sr._get_morphology(
                {}, None, None, None,
                morphlib.morphloader.MorphologyLoader(), 'reponame',
                'sha1', 'chunk.morph')
        self.assertEqual('chunk', morph['name'])

    def test_gets_morph_from_cache(self):
        self.lr.list_files = self.localmorph
        morph_from_repo = self.sr._get_morphology(
                {}, None, None, None,
                morphlib.morphloader.MorphologyLoader(), 'reponame',
                'sha1', 'chunk.morph')
        morph_from_cache = self.sr._get_morphology(
                {}, None, None, None,
                morphlib.morphloader.MorphologyLoader(), 'reponame',
                'sha1', 'chunk.morph')
        self.assertEqual(morph_from_repo, morph_from_cache)

    def test_gets_morph_from_remote_repo(self):
        self.rrc.ls_tree = self.remotemorph
        self.lrc.has_repo = self.doesnothaverepo
        morph = self.sr._get_morphology(
                {}, None, None, None,
                morphlib.morphloader.MorphologyLoader(), 'reponame',
                'sha1', 'remote-chunk.morph')
        self.assertEqual('remote-chunk', morph['name'])

    def test_autodetects_local_morphology(self):
        self.lr.read_file = self.nolocalmorph
        self.lr.list_files = self.autotoolsbuildsystem
        bs = self.sr._detect_build_system('reponame', 'sha1',
                                          'assumed-local.morph')
        self.assertEqual('autotools', bs.name)

    def test_cache_repo_if_not_in_either_cache(self):
        self.lrc.has_repo = self.doesnothaverepo
        self.lr.read_file = self.nolocalmorph
        self.lr.list_files = self.autotoolsbuildsystem
        self.rrc.ls_tree = self.noremoterepo
        bs = self.sr._detect_build_system('reponame', 'sha1',
                                          'assumed-local.morph')
        self.assertEqual('autotools', bs.name)

    def test_autodetects_remote_morphology(self):
        self.lrc.has_repo = self.doesnothaverepo
        self.rrc.cat_file = self.noremotemorph
        self.rrc.ls_tree = self.autotoolsbuildsystem
        bs = self.sr._detect_build_system('reponame', 'sha1',
                                          'assumed-remote.morph')
        self.assertEqual('autotools', bs.name)

    def test_returns_none_when_no_local_morph(self):
        self.lr.read_file = self.nolocalfile
        morph = self.sr._get_morphology(
                {}, None, None, None,
                morphlib.morphloader.MorphologyLoader(), 'reponame',
                'sha1', 'unreached.morph')
        self.assertEqual(morph, None)

    def test_returns_none_when_fails_no_remote_morph(self):
        self.lrc.has_repo = self.doesnothaverepo
        self.rrc.cat_file = self.noremotefile
        morph = self.sr._get_morphology(
                {}, None, None, None,
                morphlib.morphloader.MorphologyLoader(), 'reponame',
                'sha1', 'unreached.morph')
        self.assertEqual(morph, None)

    def test_raises_error_when_repo_does_not_exist(self):
        self.lrc.has_repo = self.doesnothaverepo
        self.assertRaises(MorphologyNotFoundError,
                          self.lsr._detect_build_system,
                          'reponame', 'sha1', 'non-existent.morph')

    def test_raises_error_when_failed_to_detect_build_system(self):
        self.lr.read_file = self.nolocalfile
        self.lr.list_files = self.emptytree
        self.assertRaises(MorphologyNotFoundError,
                          self.sr._detect_build_system,
                          'reponame', 'sha1', 'undetected.morph')

    def test_raises_error_when_name_mismatches(self):
        self.assertRaises(morphlib.Error, self.sr._get_morphology, {},
                None, None, None, morphlib.morphloader.MorphologyLoader(),
                'reponame', 'sha1', 'name-mismatch.morph')

    def test_looks_locally_with_no_remote(self):
        self.lr.list_files = self.localmorph
        morph = self.lsr._get_morphology(
                {}, None, None, None,
                morphlib.morphloader.MorphologyLoader(), 'reponame',
                'sha1', 'chunk.morph')
        self.assertEqual('chunk', morph['name'])

    def test_autodetects_locally_with_no_remote(self):
        self.lr.read_file = self.nolocalmorph
        self.lr.list_files = self.autotoolsbuildsystem
        bs = self.sr._detect_build_system('reponame', 'sha1',
                                          'assumed-local.morph')
        self.assertEqual('autotools', bs.name)

    def test_succeeds_when_local_not_cached_and_no_remote(self):
        self.lrc.has_repo = self.doesnothaverepo
        self.lr.list_files = self.localmorph
        morph = self.sr._get_morphology(
                {}, None, None, None,
                morphlib.morphloader.MorphologyLoader(), 'reponame',
                'sha1', 'chunk.morph')
        self.assertEqual('chunk', morph['name'])

    def test_arch_is_validated(self):
        self.lr.arch = 'unknown'
        self.assertRaises(morphlib.Error, self.sr._get_morphology, {},
                None, None, None, morphlib.morphloader.MorphologyLoader(),
                'reponame', 'sha1', 'system.morph')

    def test_arch_arm_defaults_to_le(self):
        self.lr.arch = 'armv7'
        morph = self.sr._get_morphology(
                {}, None, None, None,
                morphlib.morphloader.MorphologyLoader(), 'reponame',
                'sha1', 'system.morph')
        self.assertEqual(morph['arch'], 'armv7l')

    def test_fails_on_parse_error(self):
        self.assertRaises(morphlib.Error, self.sr._get_morphology, {},
                None, None, None, morphlib.morphloader.MorphologyLoader(),
                'reponame', 'sha1', 'parse-error.morph')

    def test_fails_on_no_bdeps_or_bootstrap(self):
        self.assertRaises(
            morphlib.morphloader.NoStratumBuildDependenciesError,
            self.sr._get_morphology, {}, None, None, None,
            morphlib.morphloader.MorphologyLoader(), 'reponame', 'sha1',
            'stratum-no-bdeps-no-bootstrap.morph')

    def test_succeeds_on_bdeps_no_bootstrap(self):
        self.sr._get_morphology({}, None, None, None,
            morphlib.morphloader.MorphologyLoader(), 'reponame', 'sha1',
            'stratum-bdeps-no-bootstrap.morph')

    def test_fails_on_empty_stratum(self):
        self.assertRaises(
            morphlib.morphloader.EmptyStratumError,
            self.sr._get_morphology, {}, None, None, None,
            morphlib.morphloader.MorphologyLoader(), 'reponame', 'sha1',
            'stratum-empty.morph')

