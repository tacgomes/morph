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


class GitDirectoryTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.dirname = os.path.join(self.tempdir, 'foo')

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def fake_git_clone(self):
        os.mkdir(self.dirname)
        os.mkdir(os.path.join(self.dirname, '.git'))

    def test_has_dirname_attribute(self):
        self.fake_git_clone()
        gitdir = morphlib.gitdir.GitDirectory(self.dirname)
        self.assertEqual(gitdir.dirname, self.dirname)

    def test_runs_command_in_right_directory(self):
        self.fake_git_clone()
        gitdir = morphlib.gitdir.GitDirectory(self.dirname)
        output = gitdir._runcmd(['pwd'])
        self.assertEqual(output.strip(), self.dirname)

    def test_sets_and_gets_configuration(self):
        os.mkdir(self.dirname)
        gitdir = morphlib.gitdir.init(self.dirname)
        gitdir.set_config('foo.bar', 'yoyo')
        self.assertEqual(gitdir.get_config('foo.bar'), 'yoyo')

    def test_sets_remote(self):
        os.mkdir(self.dirname)
        gitdir = morphlib.gitdir.init(self.dirname)
        self.assertEqual(gitdir.get_remote_fetch_url('origin'), None)

        gitdir._runcmd(['git', 'remote', 'add', 'origin', 'foobar'])
        url = 'git://git.example.com/foo'
        gitdir.set_remote_fetch_url('origin', url)
        self.assertEqual(gitdir.get_remote_fetch_url('origin'), url)

