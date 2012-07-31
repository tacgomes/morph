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


import os
import shutil
import tempfile
import unittest

import savefile


class SaveFileTests(unittest.TestCase):

    def cat(self, filename):
        with open(filename) as f:
            return f.read()

    def mkfile(self, filename, contents):
        with open(filename, 'w') as f:
            f.write(contents)

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.basename = 'filename'
        self.filename = os.path.join(self.tempdir, self.basename)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_there_are_no_files_initially(self):
        self.assertEqual(os.listdir(self.tempdir), [])

    def test_sets_real_filename(self):
        f = savefile.SaveFile(self.filename, 'w')
        self.assertEqual(f.real_filename, self.filename)

    def test_sets_name_to_temporary_name(self):
        f = savefile.SaveFile(self.filename, 'w')
        self.assertNotEqual(f.name, self.filename)

    def test_saves_new_file(self):
        f = savefile.SaveFile(self.filename, 'w')
        f.write('foo')
        f.close()
        self.assertEqual(os.listdir(self.tempdir), [self.basename])
        self.assertEqual(self.cat(self.filename), 'foo')

    def test_overwrites_existing_file(self):
        self.mkfile(self.filename, 'yo!')
        f = savefile.SaveFile(self.filename, 'w')
        f.write('foo')
        f.close()
        self.assertEqual(os.listdir(self.tempdir), [self.basename])
        self.assertEqual(self.cat(self.filename), 'foo')

    def test_leaves_no_file_after_aborted_new_file(self):
        f = savefile.SaveFile(self.filename, 'w')
        f.write('foo')
        f.abort()
        self.assertEqual(os.listdir(self.tempdir), [])

    def test_leaves_original_file_after_aborted_overwrite(self):
        self.mkfile(self.filename, 'yo!')
        f = savefile.SaveFile(self.filename, 'w')
        f.write('foo')
        f.abort()
        self.assertEqual(os.listdir(self.tempdir), [self.basename])
        self.assertEqual(self.cat(self.filename), 'yo!')

    def test_saves_normally_with_with(self):
        with savefile.SaveFile(self.filename, 'w') as f:
            f.write('foo')
        self.assertEqual(os.listdir(self.tempdir), [self.basename])
        self.assertEqual(self.cat(self.filename), 'foo')

    def test_saves_normally_with_exception_within_with(self):
        try:
            with savefile.SaveFile(self.filename, 'w') as f:
                f.write('foo')
                raise Exception()
        except Exception:
            pass
        self.assertEqual(os.listdir(self.tempdir), [self.basename])
        self.assertEqual(self.cat(self.filename), 'foo')
