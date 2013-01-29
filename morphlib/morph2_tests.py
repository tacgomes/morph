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


import StringIO
import unittest

import morphlib
from morphlib.morph2 import Morphology


class MorphologyTests(unittest.TestCase):

    def test_parses_simple_json_chunk(self):
        m = Morphology('''
            {
                "name": "foo",
                "kind": "chunk",
                "build-system": "manual"
            }
        ''')

        self.assertEqual(m['name'], 'foo')
        self.assertEqual(m['kind'], 'chunk')
        self.assertEqual(m['build-system'], 'manual')
        self.assertEqual(m['configure-commands'], None)
        self.assertEqual(m['build-commands'], None)
        self.assertEqual(m['test-commands'], None)
        self.assertEqual(m['install-commands'], None)
        self.assertEqual(m['max-jobs'], None)
        self.assertEqual(m['chunks'], [])

    if morphlib.got_yaml:
        def test_parses_simple_yaml_chunk(self):
            m = Morphology('''
                name: foo
                kind: chunk
                build-system: manual
            ''')

            self.assertEqual(m['name'], 'foo')
            self.assertEqual(m['kind'], 'chunk')
            self.assertEqual(m['build-system'], 'manual')
            self.assertEqual(m['configure-commands'], None)
            self.assertEqual(m['build-commands'], None)
            self.assertEqual(m['test-commands'], None)
            self.assertEqual(m['install-commands'], None)
            self.assertEqual(m['max-jobs'], None)
            self.assertEqual(m['chunks'], [])

    def test_sets_stratum_chunks_repo_and_morph_from_name(self):
        m = Morphology('''
            {
                "name": "foo",
                "kind": "stratum",
                "chunks": [
                    {
                        "name": "le-chunk",
                        "ref": "ref"
                    }
                ]
            }
        ''')

        self.assertEqual(m['chunks'][0]['repo'], 'le-chunk')
        self.assertEqual(m['chunks'][0]['morph'], 'le-chunk')
        self.assertEqual(m['chunks'][0]['build-depends'], None)

    def test_parses_system_disk_size(self):
        m = Morphology('''
            {
                "name": "foo",
                "kind": "system",
                "disk-size": "1g"
            }
        ''')

        self.assertEqual(m['disk-size'], 1024 ** 3)

    def test_returns_dict_keys(self):
        m = Morphology('''
            {
                "name": "foo",
                "kind": "system",
                "disk-size": "1g"
            }
        ''')

        self.assertTrue('name' in m.keys())
        self.assertTrue('kind' in m.keys())
        self.assertTrue('disk-size' in m.keys())

    def test_system_indexes_strata(self):
        m = Morphology('''
            {
                "kind": "system",
                "strata": [
                    {
                        "morph": "stratum1",
                        "repo": "repo",
                        "ref": "ref"
                    },
                    {
                        "alias": "aliased-stratum",
                        "morph": "stratum2",
                        "repo": "repo",
                        "ref": "ref"
                    }
                ]
            }
        ''')
        self.assertEqual(m.lookup_child_by_name('stratum1'),
                         {'morph': 'stratum1', 'repo': 'repo', 'ref': 'ref' })
        self.assertEqual(m.lookup_child_by_name('aliased-stratum'),
                         {'alias': 'aliased-stratum', 'morph': 'stratum2',
                          'repo': 'repo', 'ref': 'ref'})

    def test_stratum_indexes_chunks(self):
        m = Morphology('''
            {
                "kind": "stratum",
                "chunks": [
                    {
                        "name": "chunk",
                        "repo": "repo",
                        "ref": "ref"
                    }
                ]
            }
        ''')

        child = m.lookup_child_by_name('chunk')
        self.assertEqual(child['name'], 'chunk')
        self.assertEqual(child['repo'], 'repo')
        self.assertEqual(child['ref'], 'ref')

    def test_raises_error_when_child_lookup_fails(self):
        m = Morphology('''
            {
                "kind": "stratum",
                "chunks": [
                    {
                        "name": "chunk",
                        "repo": "repo",
                        "ref": "ref"
                    }
                ]
            }
        ''')

        self.assertRaises(KeyError, m.lookup_child_by_name, 'foo')

    ## Validation tests

    def test_makes_max_jobs_be_an_integer(self):
        m = Morphology('''
            {
                "name": "foo",
                "kind": "chunk",
                "max-jobs": "42"
            }
        ''')
        self.assertEqual(m['max-jobs'], 42)

    def test_stratum_names_must_be_unique_within_a_system(self):
        text = '''
            {
                "kind": "system",
                "strata": [
                    {
                        "morph": "stratum",
                        "repo": "test1",
                        "ref": "ref"
                    },
                    {
                        "morph": "stratum",
                        "repo": "test2",
                        "ref": "ref"
                    }
                ]
            }
        '''
        self.assertRaises(ValueError,
                          Morphology,
                          text)

    def test_chunk_names_must_be_unique_within_a_stratum(self):
        text = '''
            {
                "kind": "stratum",
                "chunks": [
                    {
                        "name": "chunk",
                        "repo": "test1",
                        "ref": "ref"
                    },
                    {
                        "name": "chunk",
                        "repo": "test2",
                        "ref": "ref"
                    }
                ]
            }
        '''
        self.assertRaises(ValueError,
                          Morphology,
                          text)

    def test_writing_preserves_field_order(self):
        text = '''{
    "kind": "system",
    "disk-size": 1073741824,
    "description": "Some text",
    "arch": "x86_64",
    "system-kind": "syslinux-disk",
    "strata": [
        {
            "morph": "foundation",
            "repo": "morphs",
            "ref": "ref"
        },
        {
            "morph": "devel",
            "repo": "morphs",
            "ref": "ref"
        }
    ]
}'''
        morphology = Morphology(text)
        output = StringIO.StringIO()
        morphology.write_to_file(output)

        text_lines = text.splitlines()
        output_lines = output.getvalue().splitlines()

        # Verify that input and output are equal.
        self.assertEqual(text_lines, output_lines)

    def test_writing_stratum_morphology_preserves_chunk_order(self):
        text = '''{
    "kind": "stratum",
    "chunks": [
        {
            "name": "foo",
            "repo": "morphs",
            "ref": "ref",
            "build-depends": []
        },
        {
            "name": "bar",
            "repo": "morphs",
            "ref": "ref",
            "build-depends": []
        }
    ]
}'''
        morphology = Morphology(text)
        output = StringIO.StringIO()
        morphology.write_to_file(output)

        text_lines = text.splitlines()
        output_lines = output.getvalue().splitlines()

        # Verify that input and output are equal.
        self.assertEqual(text_lines, output_lines)

    def test_writing_preserves_disk_size(self):
        text = '''{
    "kind": "system",
    "disk-size": "1g",
    "arch": "x86_64",
    "system-kind": "syslinux-disk"
}'''
        morphology = Morphology(text)
        output = StringIO.StringIO()
        morphology.write_to_file(output)

        text_lines = text.splitlines()
        output_lines = output.getvalue().splitlines()

        # Verify that in- and output are the same.
        self.assertEqual(text_lines, output_lines)
