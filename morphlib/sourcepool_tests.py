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


class DummySource(object):

    def __init__(self):
        self.repo_name = 'repo'
        self.original_ref = 'original/ref'
        self.sha1 = 'dummy.sha1'
        self.filename = 'dummy.morph'
        self.morphology = {}
        self.dependencies = []
        self.dependents = []


class SourcePoolTests(unittest.TestCase):

    def setUp(self):
        self.pool = morphlib.sourcepool.SourcePool()
        self.source = DummySource()

    def test_is_empty_initially(self):
        self.assertEqual(list(self.pool), [])
        self.assertEqual(len(self.pool), 0)

    def test_adds_source(self):
        self.pool.add(self.source)
        self.assertEqual(list(self.pool), [self.source])

    def test_looks_up_source(self):
        self.pool.add(self.source)
        result = self.pool.lookup(self.source.repo_name,
                                  self.source.original_ref,
                                  self.source.filename)
        self.assertEqual(result, self.source)

    def test_lookup_raises_keyerror_if_not_found(self):
        self.assertRaises(KeyError,
                          self.pool.lookup,
                          self.source.repo_name,
                          self.source.original_ref,
                          self.source.filename)

    def test_iterates_in_add_order(self):
        sources = []
        for i in range(10):
            source = DummySource()
            source.filename = str(i)
            self.pool.add(source)
            sources.append(source)
        self.assertEqual(list(self.pool), sources)
