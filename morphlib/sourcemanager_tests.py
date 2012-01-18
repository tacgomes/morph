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


import json
import StringIO
import unittest
import tempfile
import shutil
from tempfile import mkdtemp

import morphlib

class DummyApp(object):
   def __init__(self, git_base_url='.'):
        self.settings = { 'git-base-url': git_base_url }
        self.msg = lambda msg: None

class SourceManagerTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)


    def test_get_treeish_for_self(self):
	s = morphlib.sourcemanager.SourceManager(self.tempdir, DummyApp())
	t = s.get_treeish('.','41ee528492db9bd41604311b100da5a871098b3a')
	assert(t.sha == '41ee528492db9bd41604311b100da5a871098b3a')
	print t.repo

	
 	


