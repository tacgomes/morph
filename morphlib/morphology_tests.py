# Copyright (C) 2011  Codethink Limited
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
import StringIO
import unittest

import morphlib


class MockFile(StringIO.StringIO):

    def __init__(self, *args, **kwargs):
        StringIO.StringIO.__init__(self, *args, **kwargs)
        self.name = 'mockfile'


class MorphologyTests(unittest.TestCase):

    def test_accepts_valid_chunk_morphology(self):
        morph = morphlib.morphology.Morphology(
                          MockFile('''
                            {
                                "name": "hello",
                                "kind": "chunk", 
                                "description": "desc",
                                "configure-commands": ["./configure"],
                                "build-commands": ["make"],
                                "test-commands": ["make check"],
                                "install-commands": ["make install"]
                            }'''))
        self.assertEqual(morph.name, 'hello')
        self.assertEqual(morph.kind, 'chunk')
        self.assertEqual(morph.description, 'desc')
        self.assertEqual(morph.filename, 'mockfile')
        self.assertEqual(morph.configure_commands, ['./configure'])
        self.assertEqual(morph.build_commands, ['make'])
        self.assertEqual(morph.test_commands, ['make check'])
        self.assertEqual(morph.install_commands, ['make install'])

    def test_accepts_valid_stratum_morphology(self):
        morph = morphlib.morphology.Morphology(
                          MockFile('''
                            {
                                "name": "hello",
                                "kind": "stratum", 
                                "sources": 
                                    {
                                        "foo": {
                                            "ref": "ref"
                                        }
                                    }
                            }'''))
        self.assertEqual(morph.kind, 'stratum')
        self.assertEqual(morph.filename, 'mockfile')
        self.assertEqual(morph.sources,
                         {
                            'foo': { 'repo': 'foo/', 'ref': 'ref' },
                         })

    def test_accepts_valid_system_morphology(self):
        morph = morphlib.morphology.Morphology(
                          MockFile('''
                            {
                                "name": "hello",
                                "kind": "system", 
                                "disk-size": "1G",
                                "strata": [
                                    "foo",
                                    "bar"
                                ]
                            }'''))
        self.assertEqual(morph.kind, 'system')
        self.assertEqual(morph.disk_size, '1G')
        self.assertEqual(morph.strata, ['foo', 'bar'])


class StratumRepoTests(unittest.TestCase):

    def stratum(self, repo):
        return morphlib.morphology.Morphology(
                          MockFile('''
                            {
                                "name": "hello",
                                "kind": "stratum", 
                                "sources": 
                                    {
                                        "foo": {
                                            "repo": "%s",
                                            "ref": "HEAD"
                                        }
                                    }
                            }''' % repo),
                            baseurl='git://git.baserock.org/')

    def test_leaves_absolute_repo_in_source_dict_as_is(self):
        stratum = self.stratum('git://git.baserock.org/foo/')
        self.assertEqual(stratum.sources['foo']['repo'], 
                         'git://git.baserock.org/foo/')

    def test_makes_relative_repo_url_absolute_in_source_dict(self):
        stratum = self.stratum('foo')
        self.assertEqual(stratum.sources['foo']['repo'], 
                         'git://git.baserock.org/foo/')

