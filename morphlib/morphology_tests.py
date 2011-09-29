# Copyright (C) 2011  Codethink Limited
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License.
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

    def assertRaisesSchemaError(self, morph_dict):
        f = MockFile(json.dumps(morph_dict))
        self.assertRaises(morphlib.morphology.SchemaError,
                          morphlib.morphology.Morphology, f)

    def test_raises_exception_for_empty_file(self):
        self.assertRaises(ValueError, 
                          morphlib.morphology.Morphology,
                          MockFile())

    def test_raises_exception_for_file_without_kind_field(self):
        self.assertRaisesSchemaError({})

    def test_raises_exception_for_chunk_with_unknown_keys_only(self):
        self.assertRaisesSchemaError({ 'x': 'y' })

    def test_raises_exception_if_name_only(self):
        self.assertRaisesSchemaError({ 'name': 'hello' })

    def test_raises_exception_if_name_is_empty(self):
        self.assertRaisesSchemaError({ 'name': '', 'kind': 'chunk',
                                       'sources': { 'repo': 'x', 'ref': 'y' }})

    def test_raises_exception_if_kind_only(self):
        self.assertRaisesSchemaError({ 'kind': 'chunk' })

    def test_raises_exception_for_kind_that_has_unknown_kind(self):
        self.assertRaisesSchemaError({ 'name': 'hello', 'kind': 'x' })

    def test_raises_exception_for_chunk_with_nondict_source(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': [],
        })

    def test_raises_exception_for_chunk_with_empty_source(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {},
        })

    def test_raises_exception_for_chunk_without_repo_in_source(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'x': 'y'
            },
        })

    def test_raises_exception_for_chunk_with_empty_repo_in_source(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'repo': '',
                'ref': 'master'
            },
        })

    def test_raises_exception_for_chunk_without_ref_in_source(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'repo': 'foo',
            },
        })

    def test_raises_exception_for_chunk_with_empty_ref_in_source(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'repo': 'foo',
                'ref': ''
            },
        })

    def test_raises_exception_for_chunk_with_unknown_keys_in_source(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'repo': 'foo',
                'ref': 'master',
                'x': 'y'
            },
        })

    def test_raises_exception_for_chunk_with_unknown_keys(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'repo': 'foo',
                'ref': 'master'
            },
            'x': 'y'
        })

    def test_raises_exception_for_nonlist_configure_commands(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'repo': 'foo',
                'ref': 'master'
            },
            'configure-commands': 0,
        })

    def test_raises_exception_for_list_of_nonstring_configure_commands(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'repo': 'foo',
                'ref': 'master'
            },
            'configure-commands': [0],
        })

    def test_raises_exception_for_nonlist_build_commands(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'repo': 'foo',
                'ref': 'master'
            },
            'build-commands': 0,
        })

    def test_raises_exception_for_list_of_nonstring_build_commands(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'repo': 'foo',
                'ref': 'master'
            },
            'build-commands': [0],
        })

    def test_raises_exception_for_nonlist_test_commands(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'repo': 'foo',
                'ref': 'master'
            },
            'test-commands': 0,
        })

    def test_raises_exception_for_list_of_nonstring_test_commands(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'repo': 'foo',
                'ref': 'master'
            },
            'build-commands': [0],
        })

    def test_raises_exception_for_nonlist_install_commands(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'repo': 'foo',
                'ref': 'master'
            },
            'install-commands': 0,
        })

    def test_raises_exception_for_list_of_nonstring_install_commands(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'chunk',
            'source': {
                'repo': 'foo',
                'ref': 'master'
            },
            'install-commands': [0],
        })

    def test_accepts_valid_chunk_morphology(self):
        chunk = morphlib.morphology.Morphology(
                          MockFile('''
                            {
                                "name": "hello",
                                "kind": "chunk", 
                                "configure-commands": ["./configure"],
                                "build-commands": ["make"],
                                "test-commands": ["make check"],
                                "install-commands": ["make install"]
                            }'''))
        self.assertEqual(chunk.kind, 'chunk')
        self.assertEqual(chunk.filename, 'mockfile')

    def test_raises_exception_for_stratum_without_sources(self):
        self.assertRaisesSchemaError({ 'name': 'hello', 'kind': 'stratum' })

    def test_raises_exception_for_stratum_with_nondict_sources(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'stratum',
            'sources': [],
        })

    def test_raises_exception_for_stratum_with_empty_sources(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'stratum',
            'sources': {},
        })
        
    def test_raises_exception_for_stratum_with_bad_children_in_sources(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'stratum',
            'sources': {
                'foo': 0,
            },
        })

    def test_raises_exception_for_stratum_without_repo_in_sources(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'stratum',
            'sources': {
                'foo': {
                    'ref': 'master'
                }
            },
        })

    def test_raises_exception_for_stratum_with_empty_repo_in_sources(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'stratum',
            'sources': {
                'foo': {
                    'repo': '',
                    'ref': 'master'
                }
            },
        })

    def test_raises_exception_for_stratum_with_nonstring_repo_in_sources(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'stratum',
            'sources': {
                'foo': {
                    'repo': 0,
                    'ref': 'master'
                }
            },
        })

    def test_raises_exception_for_stratum_without_ref_in_sources(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'stratum',
            'sources': {
                'foo': {
                    'repo': 'foo',
                }
            },
        })

    def test_raises_exception_for_stratum_with_empty_ref_in_sources(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'stratum',
            'sources': {
                'foo': {
                    'repo': 'foo',
                    'ref': ''
                }
            },
        })

    def test_raises_exception_for_stratum_with_nonstring_ref_in_sources(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'stratum',
            'sources': {
                'foo': {
                    'repo': 'foo',
                    'ref': 0
                }
            },
        })

    def test_raises_exception_for_stratum_with_unknown_keys_in_sources(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'stratum',
            'sources': {
                'foo': {
                    'repo': 'foo',
                    'ref': 'master',
                    'x': 'y'
                }
            },
        })

    def test_raises_exception_for_stratum_with_unknown_keys(self):
        self.assertRaisesSchemaError({
            'name': 'hello', 
            'kind': 'stratum',
            'sources': {
                'foo': {
                    'repo': 'foo',
                    'ref': 'master'
                }
            },
            'x': 'y'
        })

    def test_accepts_valid_stratum_morphology(self):
        morph = morphlib.morphology.Morphology(
                          MockFile('''
                            {
                                "name": "hello",
                                "kind": "stratum", 
                                "sources": 
                                    {
                                        "foo": {
                                            "repo": "foo",
                                            "ref": "ref"
                                        }
                                    }
                            }'''))
        self.assertEqual(morph.kind, 'stratum')
        self.assertEqual(morph.filename, 'mockfile')


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

