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
import unittest

import morphlib


class FakeSubmodule(object):

    def __init__(self, **kwargs):
        for name in kwargs:
            setattr(self, name, kwargs[name])


class FakeTreeish(object):

    def __init__(self, tempdir, repo, subtreeish=None):
        self.repo = tempdir.join(repo)
        self.ref = 'master'
        self.submodules = []

        temp_repo = tempdir.join('temp_repo')

        os.mkdir(temp_repo)
        ex = morphlib.execute.Execute(temp_repo, lambda s: None)
        ex.runv(['git', 'init', '--quiet'])
        with open(os.path.join(temp_repo, 'file.txt'), 'w') as f:
            f.write('foobar\n')
        ex.runv(['git', 'add', 'file.txt'])
        ex.runv(['git', 'commit', '--quiet', '-m', 'foo'])
        
        if subtreeish is not None:
            ex.runv(['git', 'submodule', 'add', subtreeish.repo])
            path = os.path.basename(subtreeish.repo)
            self.submodules = [FakeSubmodule(repo=subtreeish.repo,
                                             ref='master',
                                             path=path,
                                             treeish=subtreeish)]
        
        ex = morphlib.execute.Execute(tempdir.dirname, lambda s: None)
        ex.runv(['git', 'clone', '-n', temp_repo, self.repo])
        
        shutil.rmtree(temp_repo)
        

class FactoryTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = morphlib.tempdir.Tempdir()
        self.factory = morphlib.builder.Factory(self.tempdir)
        
    def tearDown(self):
        self.tempdir.remove()

    def create_chunk(self):
        '''Create a simple binary chunk.'''
        
        inst = self.tempdir.join('dummy-inst')
        os.mkdir(inst)
        for x in ['bin', 'etc', 'lib']:
            os.mkdir(os.path.join(inst, x))
        
        binary = self.tempdir.join('dummy-chunk')
        ex = None # this is not actually used by the function!
        with open(binary, 'wb') as f:
            morphlib.bins.create_chunk(inst, f, ['.'], ex)
        return binary

    def test_has_no_staging_area_initially(self):
        self.assertEqual(self.factory.staging, None)
        
    def test_creates_staging_area(self):
        self.factory.create_staging()
        self.assertEqual(os.listdir(self.factory.staging), [])

    def test_removes_staging_area(self):
        self.factory.create_staging()
        staging = self.factory.staging
        self.factory.remove_staging()
        self.assertEqual(self.factory.staging, None)
        self.assertFalse(os.path.exists(staging))

    def test_unpacks_binary_from_file(self):
        binary = self.create_chunk()
        self.factory.create_staging()
        self.factory.unpack_binary_from_file(binary)
        self.assertEqual(sorted(os.listdir(self.factory.staging)),
                         sorted(['bin', 'etc', 'lib']))

    def test_removes_staging_area_with_contents(self):
        binary = self.create_chunk()
        self.factory.create_staging()
        self.factory.unpack_binary_from_file(binary)
        staging = self.factory.staging
        self.factory.remove_staging()
        self.assertEqual(self.factory.staging, None)
        self.assertFalse(os.path.exists(staging))

    def test_unpacks_onto_system(self):
    
        # We can't test this by really unpacking onto the system.
        # Instead, we rely on the fact that if the normal unpacking
        # works, the actual worker function for unpacking works, and
        # we can just verify that it gets called with the right
        # parameters.
    
        def fake_unpack(binary, dirname):
            self.dirname = dirname
    
        binary = self.create_chunk()
        self.factory._unpack_binary = fake_unpack
        self.factory.unpack_binary_from_file_onto_system(binary)
        self.assertEqual(self.dirname, '/')

    def test_unpacks_simple_sources(self):
        self.factory.create_staging()
        srcdir = self.tempdir.join('src')
        treeish = FakeTreeish(self.tempdir, 'repo')
        self.factory.unpack_sources(treeish, srcdir)
        self.assertTrue(os.path.exists(os.path.join(srcdir, 'file.txt')))

    def test_unpacks_submodules(self):
        self.factory.create_staging()
        srcdir = self.tempdir.join('src')
        subtreeish = FakeTreeish(self.tempdir, 'subrepo')
        supertreeish = FakeTreeish(self.tempdir, 'repo', subtreeish=subtreeish)
        self.factory.unpack_sources(supertreeish, srcdir)
        self.assertEqual(sorted(os.listdir(srcdir)),
                         sorted(['.git', 'file.txt', 'subrepo']))
        self.assertEqual(sorted(os.listdir(os.path.join(srcdir, 'subrepo'))),
                         sorted(['.git', 'file.txt']))

    def test_sets_timestamp_for_unpacked_files(self):
        self.factory.create_staging()
        srcdir = self.tempdir.join('src')
        treeish = FakeTreeish(self.tempdir, 'repo')
        self.factory.unpack_sources(treeish, srcdir)
        
        mtime = None
        for dirname, subdirs, basenames in os.walk(srcdir):
            pathnames = [os.path.join(dirname, x) for x in basenames]
            for pathname in pathnames + [dirname]:
                st = os.lstat(pathname)
                if mtime is None:
                    mtime = st.st_mtime
                else:
                    self.assertEqual((pathname, mtime), 
                                     (pathname, st.st_mtime))

