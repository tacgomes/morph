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

import morphlib


class MorphologyLoaderTests(unittest.TestCase):

    def test_load_twice_verify_same_morph_object(self):
        settings = { 'git-base-url': '' }
        loader = morphlib.morphologyloader.MorphologyLoader(settings)
        loader._get_morph_text = self.get_morph_text
        
        morph1 = loader.load('repo', 'ref', 'hello.morph')
        morph2 = loader.load('repo', 'ref', 'hello.morph')
        self.assertEqual(morph1, morph2)

    def get_morph_text(self, repo, ref, filename):
        return ('''
                {
                    "name": "foo",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "bar",
                            "repo": "bar",
                            "ref": "master"
                        }
                    ]
                }''')
