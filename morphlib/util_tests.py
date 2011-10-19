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


import unittest

import morphlib


class ArchTests(unittest.TestCase):

    def test(self):
        arch = morphlib.util.arch()
        self.assertEqual(type(arch), str)
        self.assertNotEqual(arch, '')


class IndentTests(unittest.TestCase):

    def test_returns_empty_string_for_empty_string(self):
        self.assertEqual(morphlib.util.indent(''), '')
        
    def test_indents_single_line(self):
        self.assertEqual(morphlib.util.indent('foo'), '    foo')

    def test_obeys_spaces_setting(self):
        self.assertEqual(morphlib.util.indent('foo', spaces=2), '  foo')

    def test_indents_multiple_lines(self):
        self.assertEqual(morphlib.util.indent('foo\nbar\n'), 
                         '    foo\n    bar')


class MakeConcurrencyTests(unittest.TestCase):

    def test_returns_2_for_1_core(self):
        self.assertEqual(morphlib.util.make_concurrency(cores=1), 2)

    def test_returns_3_for_2_cores(self):
        self.assertEqual(morphlib.util.make_concurrency(cores=2), 3)

    def test_returns_5_for_3_cores(self):
        self.assertEqual(morphlib.util.make_concurrency(cores=3), 5)

    def test_returns_6_for_4_cores(self):
        self.assertEqual(morphlib.util.make_concurrency(cores=4), 6)

