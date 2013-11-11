# Copyright (C) 2013  Codethink Limited
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
#
# =*= License: GPL-2 =*=


import os
import shutil
import tempfile
import unittest

import morphlib


class GitIndexTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.dirname = os.path.join(self.tempdir, 'foo')
        os.mkdir(self.dirname)
        gd = morphlib.gitdir.init(self.dirname)
        with open(os.path.join(self.dirname, 'foo'), 'w') as f:
            f.write('dummy text\n')
        gd._runcmd(['git', 'add', '.'])
        gd._runcmd(['git', 'commit', '-m', 'Initial commit'])
        self.mirror = os.path.join(self.tempdir, 'mirror')
        gd._runcmd(['git', 'clone', '--mirror', self.dirname, self.mirror])

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_uncommitted_changes(self):
        idx = morphlib.gitdir.GitDirectory(self.dirname).get_index()
        self.assertEqual(list(idx.get_uncommitted_changes()), [])
        os.unlink(os.path.join(self.dirname, 'foo'))
        self.assertEqual(sorted(idx.get_uncommitted_changes()),
                         [(' D', 'foo', None)])

    def test_uncommitted_alt_index(self):
        gd = morphlib.gitdir.GitDirectory(self.dirname)
        idx = gd.get_index(os.path.join(self.tempdir, 'index'))
        self.assertEqual(sorted(idx.get_uncommitted_changes()),
                         [('D ', 'foo', None)])
        # 'D ' means not in the index, but in the working tree
