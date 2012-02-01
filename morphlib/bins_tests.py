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
import stat
import tempfile
import unittest

import morphlib


class BinsTest(unittest.TestCase):

    def recursive_lstat(self, root):
        '''Return a list of (pathname, stat) pairs for everything in root.
        
        Pathnames are relative to root. Directories are recursed into.
        The stat result is selective, not all fields are used.
        
        '''
        
        def remove_root(pathname):
            self.assertTrue(pathname.startswith(root))
            if pathname == root:
                return '.'
            else:
                return pathname[len(root)+1:]
        
        def lstat(filename):
            st = os.lstat(filename)
            if stat.S_ISDIR(st.st_mode):
                return (st.st_mode, 0, 0)
            else:
                return (st.st_mode, st.st_size, st.st_mtime)
    
        result = []
        
        for dirname, subdirs, basenames in os.walk(root):
            result.append((remove_root(dirname), lstat(dirname)))
            for basename in sorted(basenames):
                filename = os.path.join(dirname, basename)
                result.append((remove_root(filename), lstat(filename)))
            subdirs.sort()
        
        return result


class ChunkTests(BinsTest):

    def setUp(self):
        self.ex = morphlib.execute.Execute('.', lambda s: None)
        self.tempdir = tempfile.mkdtemp()
        self.instdir = os.path.join(self.tempdir, 'inst')
        self.chunk_file = os.path.join(self.tempdir, 'chunk')
        self.unpacked = os.path.join(self.tempdir, 'unpacked')
        
    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def populate_instdir(self):
        timestamp = 12765

        os.mkdir(self.instdir)
        
        bindir = os.path.join(self.instdir, 'bin')
        os.mkdir(bindir)
        filename = os.path.join(bindir, 'foo')
        with open(filename, 'w'):
            pass
        os.utime(filename, (timestamp, timestamp))

        libdir = os.path.join(self.instdir, 'lib')
        os.mkdir(libdir)
        filename = os.path.join(libdir, 'libfoo.so')
        with open(filename, 'w'):
            pass
        os.utime(filename, (timestamp, timestamp))
        
    def test_empties_everything(self):
        self.populate_instdir()
        morphlib.bins.create_chunk(self.instdir, self.chunk_file, ['.'],
                                   self.ex)
        empty = os.path.join(self.tempdir, 'empty')
        os.mkdir(empty)
        self.assertEqual([x for x,y in self.recursive_lstat(self.instdir)],
                         ['.'])

    def test_creates_and_unpacks_chunk_exactly(self):
        self.populate_instdir()
        orig_files = self.recursive_lstat(self.instdir)
        morphlib.bins.create_chunk(self.instdir, self.chunk_file, ['.'],
                                   self.ex)
        os.mkdir(self.unpacked)
        morphlib.bins.unpack_binary(self.chunk_file, self.unpacked, self.ex)
        self.assertEqual(orig_files, self.recursive_lstat(self.unpacked))

    def test_uses_only_matching_names(self):
        self.populate_instdir()
        morphlib.bins.create_chunk(self.instdir, self.chunk_file, ['bin'],
                                   self.ex)
        os.mkdir(self.unpacked)
        morphlib.bins.unpack_binary(self.chunk_file, self.unpacked, self.ex)
        self.assertEqual([x for x,y in self.recursive_lstat(self.unpacked)],
                         ['.', 'bin', 'bin/foo'])
        self.assertEqual([x for x,y in self.recursive_lstat(self.instdir)],
                         ['.', 'lib', 'lib/libfoo.so'])

class StratumTests(BinsTest):

    def setUp(self):
        self.ex = morphlib.execute.Execute('.', lambda s: None)
        self.tempdir = tempfile.mkdtemp()
        self.instdir = os.path.join(self.tempdir, 'inst')
        self.stratum_file = os.path.join(self.tempdir, 'stratum')
        self.unpacked = os.path.join(self.tempdir, 'unpacked')
        
    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def populate_instdir(self):
        os.mkdir(self.instdir)
        os.mkdir(os.path.join(self.instdir, 'bin'))

    def test_creates_and_unpacks_stratum_exactly(self):
        self.populate_instdir()
        morphlib.bins.create_stratum(self.instdir, self.stratum_file, self.ex)
        os.mkdir(self.unpacked)
        morphlib.bins.unpack_binary(self.stratum_file, self.unpacked, self.ex)
        self.assertEqual(self.recursive_lstat(self.instdir),
                         self.recursive_lstat(self.unpacked))

