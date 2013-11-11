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

class GitDirectoryContentsTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.dirname = os.path.join(self.tempdir, 'foo')
        os.mkdir(self.dirname)
        gd = morphlib.gitdir.init(self.dirname)
        for fn in ('foo', 'bar.morph', 'baz.morph', 'quux'):
            with open(os.path.join(self.dirname, fn), "w") as f:
                f.write('dummy morphology text')
        gd._runcmd(['git', 'add', '.'])
        gd._runcmd(['git', 'commit', '-m', 'Initial commit'])
        os.rename(os.path.join(self.dirname, 'foo'),
                  os.path.join(self.dirname, 'foo.morph'))
        self.mirror = os.path.join(self.tempdir, 'mirror')
        gd._runcmd(['git', 'clone', '--mirror', self.dirname, self.mirror])

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_lists_files_in_work_tree(self):
        gd = morphlib.gitdir.GitDirectory(self.dirname)
        self.assertEqual(sorted(gd.list_files()),
                         ['bar.morph', 'baz.morph', 'foo.morph', 'quux'])

    def test_read_file_in_work_tree(self):
        gd = morphlib.gitdir.GitDirectory(self.dirname)
        self.assertEqual(gd.read_file('bar.morph'),
                         'dummy morphology text')

    def test_list_raises_no_ref_no_work_tree(self):
        gd = morphlib.gitdir.GitDirectory(self.mirror)
        self.assertRaises(morphlib.gitdir.NoWorkingTreeError,
                          gd.list_files)

    def test_read_raises_no_ref_no_work_tree(self):
        gd = morphlib.gitdir.GitDirectory(self.mirror)
        self.assertRaises(morphlib.gitdir.NoWorkingTreeError,
                          gd.read_file, 'bar.morph')

    def test_lists_files_in_HEAD(self):
        for gitdir in (self.dirname, self.mirror):
            gd = morphlib.gitdir.GitDirectory(gitdir)
            self.assertEqual(sorted(gd.list_files('HEAD')),
                             ['bar.morph', 'baz.morph', 'foo', 'quux'])

    def test_read_files_in_HEAD(self):
        for gitdir in (self.dirname, self.mirror):
            gd = morphlib.gitdir.GitDirectory(gitdir)
            self.assertEqual(gd.read_file('bar.morph', 'HEAD'),
                             'dummy morphology text')

    def test_lists_files_in_named_ref(self):
        for gitdir in (self.dirname, self.mirror):
            gd = morphlib.gitdir.GitDirectory(gitdir)
            self.assertEqual(sorted(gd.list_files('master')),
                             ['bar.morph', 'baz.morph', 'foo', 'quux'])

    def test_read_file_in_named_ref(self):
        for gitdir in (self.dirname, self.mirror):
            gd = morphlib.gitdir.GitDirectory(gitdir)
            self.assertEqual(gd.read_file('bar.morph', 'master'),
                             'dummy morphology text')

    def test_list_raises_invalid_ref(self):
        gd = morphlib.gitdir.GitDirectory(self.dirname)
        self.assertRaises(morphlib.gitdir.InvalidRefError,
                          gd.list_files, 'no-such-ref')

    def test_read_raises_invalid_ref(self):
        gd = morphlib.gitdir.GitDirectory(self.dirname)
        self.assertRaises(morphlib.gitdir.InvalidRefError,
                          gd.read_file, 'bar', 'no-such-ref')

    def test_HEAD(self):
        gd = morphlib.gitdir.GitDirectory(self.dirname)
        self.assertEqual(gd.HEAD, 'master')

        gd.branch('foo', 'master')
        self.assertEqual(gd.HEAD, 'master')

        gd.checkout('foo')
        self.assertEqual(gd.HEAD, 'foo')

    def test_resolve_ref(self):
        # Just tests that you get an object IDs back and that the
        # commit and tree IDs are different, since checking the actual
        # value of the commit requires foreknowledge of the result or
        # re-implementing the body in the test.
        gd = morphlib.gitdir.GitDirectory(self.dirname)
        commit = gd.resolve_ref_to_commit(gd.HEAD)
        self.assertEqual(len(commit), 40)
        tree = gd.resolve_ref_to_tree(gd.HEAD)
        self.assertEqual(len(tree), 40)
        self.assertNotEqual(commit, tree)

    def test_store_blob_with_string(self):
        gd = morphlib.gitdir.GitDirectory(self.dirname)
        sha1 = gd.store_blob('test string')
        self.assertEqual('test string', gd.get_blob_contents(sha1))

    def test_store_blob_with_file(self):
        gd = morphlib.gitdir.GitDirectory(self.dirname)
        with open(os.path.join(self.tempdir, 'blob'), 'w') as f:
            f.write('test string')
        with open(os.path.join(self.tempdir, 'blob'), 'r') as f:
            sha1 = gd.store_blob(f)
        self.assertEqual('test string', gd.get_blob_contents(sha1))

    def test_uncommitted_changes(self):
        gd = morphlib.gitdir.GitDirectory(self.dirname)
        self.assertEqual(sorted(gd.get_uncommitted_changes()),
                         [(' D', 'foo', None)])
