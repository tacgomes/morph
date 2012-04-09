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
import unittest

import morphlib

from morphlib import cachedrepo


class CachedRepoTests(unittest.TestCase):

    def show_ref(self, ref):
        output = {
            'master': 
                'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9'
                ' refs/remotes/origin/master',
            'baserock/morph':
                '8b780e2e6f102fcf400ff973396566d36d730501'
                ' refs/remotes/origin/baserock/morph',
        }
        try:
            return output[ref]
        except:
            raise morphlib.execute.CommandFailure('git show-ref %s' % ref, '')

    def rev_list(self, ref):
        output = {
            'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9': 
                'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9',
            'a4da32f5a81c8bc6d660404724cedc3bc0914a75':
                'a4da32f5a81c8bc6d660404724cedc3bc0914a75'
        }
        try:
            return output[ref]
        except:
            raise morphlib.execute.CommandFailure('git rev-list %s' % ref, '')

    def cat_file(self, ref, filename):
        output = {
            'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9:foo.morph':
                'contents of foo.morph'
        }
        try:
            return output['%s:%s' % (ref, filename)]
        except:
            raise morphlib.execute.CommandFailure(
                    'git cat-file blob %s:%s' % (ref, filename), '')

    def copy_repository(self, source_dir, target_dir):
        pass

    def checkout_ref(self, ref, target_dir):
        if ref == 'a4da32f5a81c8bc6d660404724cedc3bc0914a75':
            # simulate a git failure or something similar to
            # trigger a CheckoutError
            raise morphlib.execute.CommandFailure('git checkout %s' % ref, '')
        else:
            with open(os.path.join(target_dir, 'foo.morph'), 'w') as f:
                f.write('contents of foo.morph')

    def update_successfully(self):
        pass

    def update_with_failure(self):
        raise morphlib.execute.CommandFailure('git remote update origin', '')

    def setUp(self):
        self.repo_url = 'git://foo.bar/foo.git'
        self.repo_path = '/tmp/foo'
        self.repo = cachedrepo.CachedRepo(self.repo_url, self.repo_path)
        self.repo._show_ref = self.show_ref
        self.repo._rev_list = self.rev_list
        self.repo._cat_file = self.cat_file
        self.repo._copy_repository = self.copy_repository
        self.repo._checkout_ref = self.checkout_ref
        self.tempdir = morphlib.tempdir.Tempdir()

    def tearDown(self):
        self.tempdir.remove()

    def test_constructor_sets_url_and_path(self):
        self.assertEqual(self.repo.url, self.repo_url)
        self.assertEqual(self.repo.path, self.repo_path)

    def test_resolve_named_ref_master(self):
        sha1 = self.repo.resolve_ref('master')
        self.assertEqual(sha1, 'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')

    def test_resolve_named_ref_baserock_morph(self):
        sha1 = self.repo.resolve_ref('baserock/morph')
        self.assertEqual(sha1, '8b780e2e6f102fcf400ff973396566d36d730501')

    def test_fail_resolving_invalid_named_ref(self):
        with self.assertRaises(cachedrepo.InvalidReferenceError):
            self.repo.resolve_ref('foo/bar')

    def test_resolve_sha1_ref(self):
        sha1 = self.repo.resolve_ref(
                'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')
        self.assertEqual(sha1, 'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')

    def test_fail_resolving_an_invalid_sha1_ref(self):
        with self.assertRaises(cachedrepo.InvalidReferenceError):
            self.repo.resolve_ref('079bbfd447c8534e464ce5d40b80114c2022ebf4')

    def test_cat_existing_file_in_existing_ref(self):
        data = self.repo.cat('e28a23812eadf2fce6583b8819b9c5dbd36b9fb9',
                             'foo.morph')
        self.assertEqual(data, 'contents of foo.morph')

    def test_fail_cat_file_in_invalid_ref(self):
        with self.assertRaises(cachedrepo.InvalidReferenceError):
            self.repo.cat('079bbfd447c8534e464ce5d40b80114c2022ebf4',
                          'doesnt-matter-whether-this-file-exists')

    def test_fail_cat_non_existent_file_in_existing_ref(self):
        with self.assertRaises(IOError):
            self.repo.cat('e28a23812eadf2fce6583b8819b9c5dbd36b9fb9',
                          'file-that-does-not-exist')

    def test_fail_cat_non_existent_file_in_invalid_ref(self):
        with self.assertRaises(cachedrepo.InvalidReferenceError):
            self.repo.cat('079bbfd447c8534e464ce5d40b80114c2022ebf4',
                          'file-that-does-not-exist')

    def test_fail_because_cat_in_named_ref_is_not_allowed(self):
        with self.assertRaises(cachedrepo.UnresolvedNamedReferenceError):
            self.repo.cat('master', 'doesnt-matter-wether-this-file-exists')

    def test_fail_checkout_into_existing_directory(self):
        with self.assertRaises(cachedrepo.CheckoutDirectoryExistsError):
            self.repo.checkout('e28a23812eadf2fce6583b8819b9c5dbd36b9fb9',
                               self.tempdir.dirname)

    def test_fail_checkout_from_named_ref_which_is_not_allowed(self):
        with self.assertRaises(cachedrepo.UnresolvedNamedReferenceError):
            self.repo.checkout('master',
                               self.tempdir.join('checkout-from-named-ref'))

    def test_fail_checkout_from_invalid_ref(self):
        with self.assertRaises(cachedrepo.InvalidReferenceError):
            self.repo.checkout('079bbfd447c8534e464ce5d40b80114c2022ebf4',
                               self.tempdir.join('checkout-from-invalid-ref'))

    def test_checkout_from_existing_ref_into_new_directory(self):
        unpack_dir = self.tempdir.join('unpack-dir')
        self.repo.checkout('e28a23812eadf2fce6583b8819b9c5dbd36b9fb9',
                           unpack_dir)
        self.assertTrue(os.path.exists(unpack_dir))

        morph_filename = os.path.join(unpack_dir, 'foo.morph')
        self.assertTrue(os.path.exists(morph_filename))

    def test_fail_checkout_due_to_copy_or_checkout_problem(self):
        with self.assertRaises(cachedrepo.CheckoutError):
            self.repo.checkout('a4da32f5a81c8bc6d660404724cedc3bc0914a75',
                               self.tempdir.join('failed-checkout'))

    def test_successful_update(self):
        self.repo._update = self.update_successfully
        self.repo.update()

    def test_failing_update(self):
        self.repo._update = self.update_with_failure
        with self.assertRaises(cachedrepo.UpdateError):
            self.repo.update()
