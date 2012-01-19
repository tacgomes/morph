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
import tempfile
import shutil
import os
from urlparse import urlparse

import morphlib

class DummyApp(object):
   def __init__(self):
        self.settings = { 'git-base-url': ['.',] }
        self.msg = lambda msg: None

class SourceManagerTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass


    def test_get_sha1_treeish_for_self(self):
        tempdir = tempfile.mkdtemp()

        s = morphlib.sourcemanager.SourceManager(tempdir, DummyApp())
        t = s.get_treeish(os.getcwd(),
                          '41ee528492db9bd41604311b100da5a871098b3a')
        assert(t.sha1 == '41ee528492db9bd41604311b100da5a871098b3a')

        shutil.rmtree(tempdir)

    def test_get_sha1_treeish_for_self_twice(self):
        tempdir = tempfile.mkdtemp()

        s = morphlib.sourcemanager.SourceManager(tempdir, DummyApp())
        t = s.get_treeish(os.getcwd(),
                          '41ee528492db9bd41604311b100da5a871098b3a')
        assert(t.sha1 == '41ee528492db9bd41604311b100da5a871098b3a')

        s = morphlib.sourcemanager.SourceManager(tempdir, DummyApp())
        t = s.get_treeish(os.getcwd(),
                          '41ee528492db9bd41604311b100da5a871098b3a')
        assert(t.sha1 == '41ee528492db9bd41604311b100da5a871098b3a')

        shutil.rmtree(tempdir)

    def test_get_ref_treeish_for_self(self):
        tempdir = tempfile.mkdtemp()

        s = morphlib.sourcemanager.SourceManager(tempdir, DummyApp())
        t = s.get_treeish(os.getcwd(), 'master')
        assert(t.ref == 'refs/heads/master')

        shutil.rmtree(tempdir)

    def test_get_sha1_treeish_for_self_bundle(self):
        tempdir = tempfile.mkdtemp()
        bundle_server_loc = tempdir+'/bundle_server'
        os.mkdir(bundle_server_loc)
        bundle_name = morphlib.sourcemanager.quote_url(os.getcwd()) + '.bndl'
        shutil.copy(os.getcwd() +'/testdata/morph.bndl',
                    bundle_server_loc + '/' +bundle_name)

        app = DummyApp()
        app.settings['bundle-server'] = 'file://' + bundle_server_loc

        s = morphlib.sourcemanager.SourceManager(tempdir, app)

        def wget(url):
            path=urlparse(url).path
            shutil.copy(path, s.source_cache_dir)

        s._wget = wget

        t = s.get_treeish(os.getcwd(),
                          '41ee528492db9bd41604311b100da5a871098b3a')
        assert(t.sha1 == '41ee528492db9bd41604311b100da5a871098b3a')

        shutil.rmtree(tempdir)


    def test_get_sha1_treeish_for_self_bundle_fail(self):
        tempdir = tempfile.mkdtemp()
        app = DummyApp()
        app.settings['bundle-server'] = 'file://' + os.getcwd() +'/testdata'

        s = morphlib.sourcemanager.SourceManager(tempdir, app)

        def wget(url):
            path=urlparse(url).path
            shutil.copy(path, s.source_cache_dir)

        s._wget = wget
        self.assertRaises(morphlib.sourcemanager.SourceNotFound, s.get_treeish,
                          'asdf','41ee528492db9bd41604311b100da5a871098b3a')

        shutil.rmtree(tempdir)

    def test_get_sha1_treeish_for_self_multple_base(self):

        tempdir = tempfile.mkdtemp()
        app = DummyApp()
        app.settings['git-base-url'] = ['.', '/somewhere/else']


        s = morphlib.sourcemanager.SourceManager(tempdir, app) 
        t = s.get_treeish(os.getcwd(),
                          '41ee528492db9bd41604311b100da5a871098b3a')
        assert(t.sha1 == '41ee528492db9bd41604311b100da5a871098b3a')

        shutil.rmtree(tempdir)


