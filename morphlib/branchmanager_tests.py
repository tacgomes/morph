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


import cliapp
import os
import shutil
import tempfile
import unittest

import morphlib


class LocalRefManagerTests(unittest.TestCase):

    REPO_COUNT = 3
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.repos = []
        for i in xrange(self.REPO_COUNT):
            dirname = os.path.join(self.tempdir, 'repo%d' % i)
            os.mkdir(dirname)
            gd = morphlib.gitdir.init(dirname)
            with open(os.path.join(dirname, 'foo'), 'w') as f:
                f.write('dummy text\n')
            gd._runcmd(['git', 'add', '.'])
            gd._runcmd(['git', 'commit', '-m', 'Initial commit'])
            gd._runcmd(['git', 'checkout', '-b', 'dev-branch'])
            with open(os.path.join(dirname, 'foo'), 'w') as f:
                f.write('updated text\n')
            gd._runcmd(['git', 'add', '.'])
            gd._runcmd(['git', 'commit', '-m', 'Second commit'])
            self.repos.append(gd)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    @staticmethod
    def lrm(*args, **kwargs):
        return morphlib.branchmanager.LocalRefManager(*args, **kwargs)

    def test_refs_added(self):
        refinfo = []
        with self.lrm() as lrm:
            for i, gd in enumerate(self.repos):
                commit = gd.resolve_ref_to_commit('refs/heads/master')
                refinfo.append(commit)
                lrm.add(gd, 'refs/heads/create%d' % i, commit)
        for i, gd in enumerate(self.repos):
            self.assertEqual(gd.resolve_ref_to_commit(
                                 'refs/heads/create%d' % i),
                             refinfo[i])

    def test_add_rollback(self):
        with self.assertRaises(Exception):
            with self.lrm() as lrm:
                for i, gd in enumerate(self.repos):
                    commit = gd.resolve_ref_to_commit('refs/heads/master')
                    lrm.add(gd, 'refs/heads/create%d' % i, commit)
                raise Exception()
        for i, gd in enumerate(self.repos):
            with self.assertRaises(morphlib.gitdir.InvalidRefError):
                gd.resolve_ref_to_commit('refs/heads/create%d' % i)

    def test_add_rollback_on_success(self):
        with self.lrm(True) as lrm:
            for i, gd in enumerate(self.repos):
                commit = gd.resolve_ref_to_commit('refs/heads/master')
                lrm.add(gd, 'refs/heads/create%d' % i, commit)
        for i, gd in enumerate(self.repos):
            with self.assertRaises(morphlib.gitdir.InvalidRefError):
                gd.resolve_ref_to_commit('refs/heads/create%d' % i)

    def test_add_rollback_deferred(self):
        with self.lrm(False) as lrm:
            for i, gd in enumerate(self.repos):
                commit = gd.resolve_ref_to_commit('refs/heads/master')
                lrm.add(gd, 'refs/heads/create%d' % i, commit)
        lrm.close()
        for i, gd in enumerate(self.repos):
            with self.assertRaises(morphlib.gitdir.InvalidRefError):
                gd.resolve_ref_to_commit('refs/heads/create%d' % i)

    def test_add_rollback_failure(self):
        failure_exception = Exception()
        with self.assertRaises(morphlib.branchmanager.RefCleanupError) as cm:
            with self.lrm() as lrm:
                for i, gd in enumerate(self.repos):
                    ref = 'refs/heads/create%d' % i
                    commit = gd.resolve_ref_to_commit('refs/heads/master')
                    lrm.add(gd, ref, commit)
                    # Make changes independent of LRM, so that rollback fails
                    new_commit = gd.resolve_ref_to_commit(
                        'refs/heads/dev-branch')
                    gd.update_ref(ref, new_commit, commit)
                raise failure_exception
        self.assertEqual(cm.exception.primary_exception, failure_exception)
        self.assertEqual([e.__class__ for _, _, e in cm.exception.exceptions],
                         [morphlib.gitdir.RefDeleteError] * self.REPO_COUNT)

    def test_refs_updated(self):
        refinfo = []
        with self.lrm() as lrm:
            for i, gd in enumerate(self.repos):
                old_master = gd.resolve_ref_to_commit('refs/heads/master')
                commit = gd.resolve_ref_to_commit('refs/heads/dev-branch')
                refinfo.append(commit)
                lrm.update(gd, 'refs/heads/master', commit, old_master)
        for i, gd in enumerate(self.repos):
            self.assertEqual(gd.resolve_ref_to_commit('refs/heads/master'),
                             refinfo[i])

    def test_update_rollback(self):
        refinfo = []
        with self.assertRaises(Exception):
            with self.lrm() as lrm:
                for i, gd in enumerate(self.repos):
                    old_master = gd.resolve_ref_to_commit('refs/heads/master')
                    commit = gd.resolve_ref_to_commit('refs/heads/dev-branch')
                    refinfo.append(old_master)
                    lrm.update(gd, 'refs/heads/master', commit, old_master)
                raise Exception()
        for i, gd in enumerate(self.repos):
            self.assertEqual(gd.resolve_ref_to_commit('refs/heads/master'),
                             refinfo[i])

    def test_update_rollback_on_success(self):
        refinfo = []
        with self.lrm(True) as lrm:
            for i, gd in enumerate(self.repos):
                old_master = gd.resolve_ref_to_commit('refs/heads/master')
                commit = gd.resolve_ref_to_commit('refs/heads/dev-branch')
                refinfo.append(old_master)
                lrm.update(gd, 'refs/heads/master', commit, old_master)
        for i, gd in enumerate(self.repos):
            self.assertEqual(gd.resolve_ref_to_commit('refs/heads/master'),
                             refinfo[i])

    def test_update_rollback_deferred(self):
        refinfo = []
        with self.lrm(False) as lrm:
            for i, gd in enumerate(self.repos):
                old_master = gd.resolve_ref_to_commit('refs/heads/master')
                commit = gd.resolve_ref_to_commit('refs/heads/dev-branch')
                refinfo.append(old_master)
                lrm.update(gd, 'refs/heads/master', commit, old_master)
        lrm.close()
        for i, gd in enumerate(self.repos):
            self.assertEqual(gd.resolve_ref_to_commit('refs/heads/master'),
                             refinfo[i])

    def test_update_rollback_failure(self):
        failure_exception = Exception()
        with self.assertRaises(morphlib.branchmanager.RefCleanupError) as cm:
            with self.lrm() as lrm:
                for i, gd in enumerate(self.repos):
                    old_master = gd.resolve_ref_to_commit('refs/heads/master')
                    commit = gd.resolve_ref_to_commit('refs/heads/dev-branch')
                    lrm.update(gd, 'refs/heads/master', commit, old_master)
                    # Delete the ref, so rollback fails
                    gd.delete_ref('refs/heads/master', commit)
                raise failure_exception
        self.assertEqual(cm.exception.primary_exception, failure_exception)
        self.assertEqual([e.__class__ for _, _, e in cm.exception.exceptions],
                         [morphlib.gitdir.RefUpdateError] * self.REPO_COUNT)

    def test_refs_deleted(self):
        with self.lrm() as lrm:
            for i, gd in enumerate(self.repos):
                commit = gd.resolve_ref_to_commit('refs/heads/master')
                lrm.delete(gd, 'refs/heads/master', commit)
        for i, gd in enumerate(self.repos):
            self.assertRaises(morphlib.gitdir.InvalidRefError,
                              gd.resolve_ref_to_commit, 'refs/heads/master')

    def test_delete_rollback(self):
        refinfo = []
        with self.assertRaises(Exception):
            with self.lrm() as lrm:
                for i, gd in enumerate(self.repos):
                    commit = gd.resolve_ref_to_commit('refs/heads/master')
                    refinfo.append(commit)
                    lrm.delete(gd, 'refs/heads/master', commit)
                raise Exception()
        for i, gd in enumerate(self.repos):
            self.assertEqual(gd.resolve_ref_to_commit('refs/heads/master'),
                             refinfo[i])

    def test_delete_rollback_on_success(self):
        refinfo = []
        with self.lrm(True) as lrm:
            for i, gd in enumerate(self.repos):
                commit = gd.resolve_ref_to_commit('refs/heads/master')
                refinfo.append(commit)
                lrm.delete(gd, 'refs/heads/master', commit)
        for i, gd in enumerate(self.repos):
            self.assertEqual(gd.resolve_ref_to_commit('refs/heads/master'),
                             refinfo[i])

    def test_delete_rollback_deferred(self):
        refinfo = []
        with self.lrm(False) as lrm:
            for i, gd in enumerate(self.repos):
                commit = gd.resolve_ref_to_commit('refs/heads/master')
                refinfo.append(commit)
                lrm.delete(gd, 'refs/heads/master', commit)
        lrm.close()
        for i, gd in enumerate(self.repos):
            self.assertEqual(gd.resolve_ref_to_commit('refs/heads/master'),
                             refinfo[i])

    def test_delete_rollback_failure(self):
        failure_exception = Exception()
        with self.assertRaises(morphlib.branchmanager.RefCleanupError) as cm:
            with self.lrm() as lrm:
                for gd in self.repos:
                    commit = gd.resolve_ref_to_commit('refs/heads/master')
                    lrm.delete(gd, 'refs/heads/master', commit)
                    gd.add_ref('refs/heads/master', commit)
                raise failure_exception
        self.assertEqual(cm.exception.primary_exception, failure_exception)
        self.assertEqual([e.__class__ for _, _, e in cm.exception.exceptions],
                         [morphlib.gitdir.RefAddError] * self.REPO_COUNT)


class RemoteRefManagerTests(unittest.TestCase):

    TARGET_COUNT = 2
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.source = os.path.join(self.tempdir, 'source')
        os.mkdir(self.source)
        self.sgd = morphlib.gitdir.init(self.source)
        with open(os.path.join(self.source, 'foo'), 'w') as f:
            f.write('dummy text\n')
        self.sgd._runcmd(['git', 'add', '.'])
        self.sgd._runcmd(['git', 'commit', '-m', 'Initial commit'])
        self.sgd._runcmd(['git', 'checkout', '-b', 'dev-branch'])
        with open(os.path.join(self.source, 'foo'), 'w') as f:
            f.write('updated text\n')
        self.sgd._runcmd(['git', 'add', '.'])
        self.sgd._runcmd(['git', 'commit', '-m', 'Second commit'])
        self.sgd._runcmd(['git', 'checkout', '--orphan', 'no-ff'])
        with open(os.path.join(self.source, 'foo'), 'w') as f:
            f.write('parallel dimension text\n')
        self.sgd._runcmd(['git', 'add', '.'])
        self.sgd._runcmd(['git', 'commit', '-m', 'Non-fast-forward commit'])

        self.remotes = []
        for i in xrange(self.TARGET_COUNT):
            name = 'remote-%d' % i
            dirname = os.path.join(self.tempdir, name)

            # Allow deleting HEAD
            cliapp.runcmd(['git', 'init', '--bare', dirname])
            gd = morphlib.gitdir.GitDirectory(dirname)
            gd.set_config('receive.denyDeleteCurrent', 'warn')

            self.sgd._runcmd(['git', 'remote', 'add', name, dirname])
            self.remotes.append((name, dirname, gd))

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    @staticmethod
    def list_refs(gd):
        out = gd._runcmd(['git', 'for-each-ref',
                          '--format=%(refname)%00%(objectname)%00'])
        return dict(line.split('\0') for line in
                    out.strip('\0\n').split('\0\n') if line)

    def push_creates(self, rrm):
        for name, dirname, gd in self.remotes:
            rrm.push(self.sgd.get_remote(name),
                     morphlib.gitdir.RefSpec('refs/heads/master'),
                     morphlib.gitdir.RefSpec('refs/heads/dev-branch'))

    def push_deletes(self, rrm):
        null_commit = '0' * 40
        master_commit = self.sgd.resolve_ref_to_commit('refs/heads/master')
        dev_commit = self.sgd.resolve_ref_to_commit('refs/heads/dev-branch')
        for name, dirname, gd in self.remotes:
            rrm.push(self.sgd.get_remote(name),
                     morphlib.gitdir.RefSpec(
                         source=null_commit,
                         target='refs/heads/master',
                         require=master_commit),
                     morphlib.gitdir.RefSpec(
                         source=null_commit,
                         target='refs/heads/dev-branch',
                         require=dev_commit))

    def assert_no_remote_branches(self):
        for name, dirname, gd in self.remotes:
            self.assertEqual(self.list_refs(gd), {})

    def assert_remote_branches(self):
        for name, dirname, gd in self.remotes:
            for name, sha1 in self.list_refs(gd).iteritems():
                self.assertEqual(self.sgd.resolve_ref_to_commit(name), sha1)

    def test_rollback_after_create_success(self):
        with morphlib.branchmanager.RemoteRefManager() as rrm:
            self.push_creates(rrm)
            self.assert_remote_branches()
        self.assert_no_remote_branches()

    def test_keep_after_create_success(self):
        with morphlib.branchmanager.RemoteRefManager(False) as rrm:
            self.push_creates(rrm)
        self.assert_remote_branches()

    def test_deferred_rollback_after_create_success(self):
        with morphlib.branchmanager.RemoteRefManager(False) as rrm:
            self.push_creates(rrm)
        rrm.close()
        self.assert_no_remote_branches()

    def test_rollback_after_create_failure(self):
        failure_exception = Exception()
        with self.assertRaises(Exception) as cm:
            with morphlib.branchmanager.RemoteRefManager() as rrm:
                self.push_creates(rrm)
                raise failure_exception
        self.assertEqual(cm.exception, failure_exception)
        self.assert_no_remote_branches()

    @unittest.skip('No way to have conditional delete until Git 1.8.5')
    def test_rollback_after_create_cleanup_failure(self):
        failure_exception = Exception()
        with self.assertRaises(morphlib.branchmanager.RefCleanupError) as cm:
            with morphlib.branchmanager.RemoteRefManager() as rrm:
                self.push_creates(rrm)

                # Break rollback with a new non-ff commit on master
                no_ff = self.sgd.resolve_ref_to_commit('no-ff')
                master = 'refs/heads/master'
                master_commit = \
                    self.sgd.resolve_ref_to_commit('refs/heads/master')
                for name, dirname, gd in self.remotes:
                    r = self.sgd.get_remote(name)
                    r.push(morphlib.gitdir.RefSpec(source=no_ff, target=master,
                                                   require=master_commit,
                                                   force=True))

                raise failure_exception
        self.assertEqual(cm.exception.primary_exception, failure_exception)
        self.assert_no_remote_branches()

    def test_rollback_after_deletes_success(self):
        for name, dirname, gd in self.remotes:
            self.sgd.get_remote(name).push(
                 morphlib.gitdir.RefSpec('master'),
                 morphlib.gitdir.RefSpec('dev-branch'))
        self.assert_remote_branches()
        with morphlib.branchmanager.RemoteRefManager() as rrm:
            self.push_deletes(rrm)
            self.assert_no_remote_branches()
        self.assert_remote_branches()

    def test_keep_after_deletes_success(self):
        for name, dirname, gd in self.remotes:
            self.sgd.get_remote(name).push(
                 morphlib.gitdir.RefSpec('master'),
                 morphlib.gitdir.RefSpec('dev-branch'))
        self.assert_remote_branches()
        with morphlib.branchmanager.RemoteRefManager(False) as rrm:
            self.push_deletes(rrm)
        self.assert_no_remote_branches()

    def test_deferred_rollback_after_deletes_success(self):
        for name, dirname, gd in self.remotes:
            self.sgd.get_remote(name).push(
                 morphlib.gitdir.RefSpec('master'),
                 morphlib.gitdir.RefSpec('dev-branch'))
        self.assert_remote_branches()
        with morphlib.branchmanager.RemoteRefManager(False) as rrm:
            self.push_deletes(rrm)
        rrm.close()
        self.assert_remote_branches()

    def test_rollback_after_deletes_failure(self):
        failure_exception = Exception()
        for name, dirname, gd in self.remotes:
            self.sgd.get_remote(name).push(
                 morphlib.gitdir.RefSpec('master'),
                 morphlib.gitdir.RefSpec('dev-branch'))
        self.assert_remote_branches()
        with self.assertRaises(Exception) as cm:
            with morphlib.branchmanager.RemoteRefManager() as rrm:
                self.push_deletes(rrm)
                raise failure_exception
        self.assertEqual(cm.exception, failure_exception)
        self.assert_remote_branches()

    def test_rollback_after_deletes_cleanup_failure(self):
        failure_exception = Exception()
        for name, dirname, gd in self.remotes:
            self.sgd.get_remote(name).push(
                 morphlib.gitdir.RefSpec('master'),
                 morphlib.gitdir.RefSpec('dev-branch'))
        with self.assertRaises(morphlib.branchmanager.RefCleanupError) as cm:
            with morphlib.branchmanager.RemoteRefManager() as rrm:
                self.push_deletes(rrm)

                # Break rollback with a new non-ff commit on master
                no_ff = self.sgd.resolve_ref_to_commit('no-ff')
                master = 'refs/heads/master'
                master_commit = \
                    self.sgd.resolve_ref_to_commit('refs/heads/master')
                for name, dirname, gd in self.remotes:
                    r = self.sgd.get_remote(name)
                    r.push(morphlib.gitdir.RefSpec(source=no_ff, target=master,
                                                   require=master_commit))

                raise failure_exception
        self.assertEqual(cm.exception.primary_exception, failure_exception)

