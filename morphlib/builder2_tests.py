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


import json
import os
import StringIO
import unittest

import morphlib


class FakeBuildSystem(object):

    def __init__(self):
        self.build_commands = ['buildsys-it']


class FakeStagingArea(object):

    def __init__(self, runcmd):
        self.runcmd = runcmd


class FakeSource(object):
    
    def __init__(self):
        self.morphology = {
            'name': 'a',
            'kind': 'b',
            'description': 'c',
        }
        
        self.repo = morphlib.cachedrepo.CachedRepo('repo', 'url', 'path')
        self.original_ref = 'e'
        self.sha1 = 'f'
        self.filename = 'g'


class FakeArtifact(object):

    def __init__(self, name):
        self.name = name
        self.source = FakeSource()
        self.cache_key = 'blahblah'


class FakeBuildEnv(object):

    def __init__(self):
        self.arch = 'le-arch'
        self.env = {
            'PATH': '/le-bin:/le-bon:/le-bin-bon',
        }


class BuilderBaseTests(unittest.TestCase):

    def fake_runcmd(self, argv, *args, **kwargs):
        self.commands_run.append(argv)

    def fake_open(self, filename, mode):
        self.open_filename = filename
        self.open_handle = StringIO.StringIO()
        self.open_handle.close = lambda: None
        return self.open_handle

    def setUp(self):
        self.commands_run = []
        self.staging_area = FakeStagingArea(self.fake_runcmd)
        self.artifact_cache = None # Not used by tests
        self.artifact = FakeArtifact('le-artifact')
        self.build_env = FakeBuildEnv()
        self.max_jobs = 1
        self.builder = morphlib.builder2.BuilderBase(self.staging_area,
                                                     self.artifact_cache,
                                                     self.artifact,
                                                     self.build_env,
                                                     self.max_jobs)

    def test_returns_an_artifact(self):
        artifact = self.builder.new_artifact('le-artifact')
        self.assertEqual(type(artifact), morphlib.artifact.Artifact)

    def test_runs_desired_command(self):
        self.builder.runcmd(['foo', 'bar'])
        self.assertEqual(self.commands_run, [['foo', 'bar']])

    def test_creates_metadata_with_required_fields(self):
        artifact_name = 'le-artifact'
        source = self.artifact.source
        morphology = source.morphology
        meta = self.builder.create_metadata(artifact_name)
        self.assertEqual(meta['artifact-name'], artifact_name)
        self.assertEqual(meta['source-name'], morphology['name'])
        self.assertEqual(meta['kind'], morphology['kind'])
        self.assertEqual(meta['description'], morphology['description'])
        self.assertEqual(meta['repo'], source.repo.url)
        self.assertEqual(meta['original_ref'], source.original_ref)
        self.assertEqual(meta['sha1'], source.sha1)
        self.assertEqual(meta['morphology'], source.filename)

    def test_writes_metadata(self):
        artifact_name = 'le-artifact'
        orig_meta = self.builder.create_metadata(artifact_name)
 
        instdir = '/inst/dir'

        self.builder._open = self.fake_open
        self.builder.write_metadata(instdir, artifact_name)

        self.assertTrue(self.open_filename.startswith(
                         os.path.join(instdir, 'baserock', 
                                      artifact_name + '.')))
        self.assertTrue(self.open_filename.endswith('.meta'))
        
        meta = json.loads(self.open_handle.getvalue())
        self.assertEqual(meta, orig_meta)


class ChunkBuilderTests(unittest.TestCase):

    def setUp(self):
        self.build = morphlib.builder2.ChunkBuilder(None, None, None, None, 1)

    def test_uses_morphology_commands_when_given(self):
        m = { 'build-commands': ['build-it'] }
        bs = FakeBuildSystem()
        cmds = self.build.get_commands('build-commands', m, bs)
        self.assertEqual(cmds, ['build-it'])

    def test_uses_build_system_commands_when_morphology_doesnt(self):
        m = { 'build-commands': None }
        bs = FakeBuildSystem()
        cmds = self.build.get_commands('build-commands', m, bs)
        self.assertEqual(cmds, ['buildsys-it'])

    def test_uses_morphology_commands_when_morphology_has_empty_list(self):
        m = { 'build-commands': [] }
        bs = FakeBuildSystem()
        cmds = self.build.get_commands('build-commands', m, bs)
        self.assertEqual(cmds, [])

