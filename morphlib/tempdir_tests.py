# Copyright (C) 2011-2012  Codethink Limited
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


import os
import shutil
import unittest

import morphlib


class TempdirTests(unittest.TestCase):

    def setUp(self):
        self.parent = os.path.abspath('unittest-tempdir')
        os.mkdir(self.parent)
        self.tempdir = morphlib.tempdir.Tempdir(parent=self.parent)

    def tearDown(self):
        shutil.rmtree(self.parent)

    def test_creates_the_directory(self):
        self.assert_(os.path.isdir(self.tempdir.dirname))

    def test_creates_subdirectory_of_parent(self):
        self.assert_(self.tempdir.dirname.startswith(self.parent + '/'))

    def test_uses_default_if_parent_not_specified(self):
        t = morphlib.tempdir.Tempdir()
        shutil.rmtree(t.dirname)
        self.assertNotEqual(t.dirname, None)

    def test_removes_itself(self):
        dirname = self.tempdir.dirname
        self.tempdir.remove()
        self.assertEqual(self.tempdir.dirname, None)
        self.assertFalse(os.path.exists(dirname))

    def test_joins_filename(self):
        self.assertEqual(self.tempdir.join('foo'), 
                         os.path.join(self.tempdir.dirname, 'foo'))

    def test_joins_absolute_filename(self):
        self.assertEqual(self.tempdir.join('/foo'), 
                         os.path.join(self.tempdir.dirname, 'foo'))

