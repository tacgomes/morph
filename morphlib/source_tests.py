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


class SourceTests(unittest.TestCase):

    morphology_text = '''
        {
            "name": "foo",
            "kind": "chunk"
        }
    '''

    def setUp(self):
        self.repo = 'foo.repo'
        self.sha1 = 'CAFEF00D'
        self.morphology = morphlib.morph2.Morphology(self.morphology_text)
        self.filename = 'foo.morph'
        self.source = morphlib.source.Source(self.repo, self.sha1,
                                             self.morphology, self.filename)
        self.other = morphlib.source.Source(self.repo, self.sha1, 
                                            self.morphology, self.filename)
                                             
    def test_sets_repo(self):
        self.assertEqual(self.source.repo, self.repo)
                                             
    def test_sets_sha1(self):
        self.assertEqual(self.source.sha1, self.sha1)
                                             
    def test_sets_morphology(self):
        self.assertEqual(self.source.morphology, self.morphology)
                                             
    def test_sets_filename(self):
        self.assertEqual(self.source.filename, self.filename)
                                             
    def test_sets_dependencies_to_empty(self):
        self.assertEqual(self.source.dependencies, [])
                                             
    def test_sets_dependents_to_empty(self):
        self.assertEqual(self.source.dependents, [])

    def test_does_not_depend_on_other_initially(self):
        self.assertFalse(self.source.depends_on(self.other))

    def test_adds_dependency(self):
        self.source.add_dependency(self.other)
        self.assertEqual(self.source.dependencies, [self.other])
        self.assertEqual(self.other.dependents, [self.source])
        self.assertTrue(self.source.depends_on(self.other))

    def test_does_not_add_dependency_twice(self):
        self.source.add_dependency(self.other)
        self.source.add_dependency(self.other)
        self.assertEqual(self.source.dependencies, [self.other])
        self.assertEqual(self.other.dependents, [self.source])
        self.assertTrue(self.source.depends_on(self.other))

