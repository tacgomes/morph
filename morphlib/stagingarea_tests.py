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
import tarfile
import tempfile
import unittest

import morphlib


class StagingAreaTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.staging = os.path.join(self.tempdir, 'staging')
        self.sa = morphlib.stagingarea.StagingArea(self.staging)

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        
    def create_chunk(self):
        chunkdir = os.path.join(self.tempdir, 'chunk')
        os.mkdir(chunkdir)
        with open(os.path.join(chunkdir, 'file.txt'), 'w'):
            pass
        chunk_tar = os.path.join(self.tempdir, 'chunk.tar')
        tf = tarfile.TarFile(name=chunk_tar, mode='w')
        tf.add(chunkdir, arcname='.')
        tf.close()
        
        return chunk_tar
        
    def list_tree(self, root):
        files = []
        for dirname, subdirs, basenames in os.walk(root):
            paths = [os.path.join(dirname, x) for x in basenames]
            for x in [dirname] + sorted(paths):
                files.append(x[len(root):] or '/')
        return files

    def test_remembers_specified_directory(self):
        self.assertEqual(self.sa.dirname, self.staging)

    def test_accepts_root_directory(self):
        sa = morphlib.stagingarea.StagingArea('/')
        self.assertEqual(sa.dirname, '/')
        
    def test_installs_artifact(self):
        chunk_tar = self.create_chunk()
        with open(chunk_tar, 'rb') as f:
            self.sa.install_artifact(f)
        self.assertEqual(self.list_tree(self.staging), ['/', '/file.txt'])

    def test_removes_everything(self):
        chunk_tar = self.create_chunk()
        with open(chunk_tar, 'rb') as f:
            self.sa.install_artifact(f)
        self.sa.remove()
        self.assertFalse(os.path.exists(self.staging))

