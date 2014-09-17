# Copyright (C) 2012-2014  Codethink Limited
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


import copy
import unittest

import morphlib


class ArtifactTests(unittest.TestCase):

    def setUp(self):
        loader = morphlib.morphloader.MorphologyLoader()
        morph = loader.load_from_string(
                '''
                name: chunk
                kind: chunk
                products:
                    - artifact: chunk-runtime
                      include:
                        - usr/bin
                        - usr/sbin
                        - usr/lib
                        - usr/libexec
                    - artifact: chunk-devel
                      include:
                        - usr/include
                ''')
        self.source, = morphlib.source.make_sources('repo', 'ref',
                                                    'chunk.morph', 'sha1',
                                                    'tree', morph)
        self.artifact_name = 'chunk-runtime'
        self.artifact = self.source.artifacts[self.artifact_name]
        self.other_source, = morphlib.source.make_sources('repo', 'ref',
                                                          'chunk.morph',
                                                          'sha1', 'tree',
                                                          morph)
        self.other = self.other_source.artifacts[self.artifact_name]

    def test_constructor_sets_source(self):
        self.assertEqual(self.artifact.source, self.source)

    def test_constructor_sets_name(self):
        self.assertEqual(self.artifact.name, self.artifact_name)

    def test_sets_dependents_to_empty(self):
        self.assertEqual(self.artifact.dependents, [])
