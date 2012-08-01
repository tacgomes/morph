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


import unittest

from morphlib.morph2 import Morphology


class MorphologyTests(unittest.TestCase):

    def test_parses_simple_chunk(self):
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
        self.assertEqual(m['chunks'], {})

    def test_makes_max_jobs_be_an_integer(self):
        m = Morphology('''
            {
                "name": "foo",
                "kind": "chunk",
                "max-jobs": "42"
            }
        ''')

        self.assertEqual(m['max-jobs'], 42)

    def test_sets_stratum_sources_repo_and_morph_from_name(self):
        m = Morphology('''
            {
                "name": "foo",
                "kind": "stratum",
                "sources": [
                    {
                        "name": "le-chunk"
                    }
                ]
            }
        ''')

        self.assertEqual(m['sources'][0]['repo'], 'le-chunk')
        self.assertEqual(m['sources'][0]['morph'], 'le-chunk')
        self.assertEqual(m['sources'][0]['build-depends'], None)

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
