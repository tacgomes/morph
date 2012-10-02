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


import cliapp
import logging
import os

import morphlib


class InvalidReferenceError(cliapp.AppException):

    def __init__(self, repo, ref):
        cliapp.AppException.__init__(
            self, 'Ref %s is an invalid reference for repo %s' % (ref, repo))


class UnresolvedNamedReferenceError(cliapp.AppException):

    def __init__(self, repo, ref):
        cliapp.AppException.__init__(
            self, 'Ref %s is not a SHA1 ref for repo %s' % (ref, repo))


class CheckoutDirectoryExistsError(cliapp.AppException):

    def __init__(self, repo, target_dir):
        cliapp.AppException.__init__(
            self,
            'Checkout directory %s for repo %s already exists' %
            (target_dir, repo))


class CloneError(cliapp.AppException):

    def __init__(self, repo, target_dir):
        cliapp.AppException.__init__(
            self,
            'Failed to clone %s into %s' % (repo.original_name, target_dir))


class CopyError(cliapp.AppException):

    def __init__(self, repo, target_dir):
        cliapp.AppException.__init__(
            self,
            'Failed to copy %s into %s' % (repo.original_name, target_dir))


class CheckoutError(cliapp.AppException):

    def __init__(self, repo, ref, target_dir):
        cliapp.AppException.__init__(
            self,
            'Failed to check out ref %s in %s' % (ref, target_dir))


class UpdateError(cliapp.AppException):

    def __init__(self, repo):
        cliapp.AppException.__init__(
            self, 'Failed to update cached version of repo %s' % repo)


class CachedRepo(object):

    '''A locally cached Git repository with an origin remote set up.

    On instance of this class represents a locally cached version of a
    remote Git repository. This remote repository is set up as the
    'origin' remote.

    Cached repositories are bare mirrors of the upstream.  Locally created
    branches will be lost the next time the repository updates.

    CachedRepo objects can resolve Git refs into SHA1s. Given a SHA1
    ref, they can also be asked to return the contents of a file via the
    cat() method. They can furthermore check out the repository into
    a local directory using a SHA1 ref. Last but not least, any cached
    repo may be updated from it's origin remote using the update()
    method.

    '''

    def __init__(self, app, original_name, url, path):
        '''Creates a new CachedRepo for a repo name, URL and local path.'''

        self.app = app
        self.original_name = original_name
        self.url = url
        self.path = path

    def resolve_ref(self, ref):
        '''Attempts to resolve a ref into its SHA1 and tree SHA1.

        Raises an InvalidReferenceError if the ref is not found in the
        repository.

        '''

        if not morphlib.git.is_valid_sha1(ref):
            try:
                refs = self._show_ref(ref).split('\n')
                refs = [x.split() for x in refs]
                absref = refs[0][0]
            except cliapp.AppException:
                raise InvalidReferenceError(self, ref)
        else:
            try:
                absref = self._rev_list(ref).strip()
            except cliapp.AppException:
                raise InvalidReferenceError(self, ref)

        tree = self._show_tree_hash(absref)
        return absref, tree

    def cat(self, ref, filename):
        '''Attempts to read a file given a SHA1 ref.

        Raises an UnresolvedNamedReferenceError if the ref is not a SHA1
        ref. Raises an InvalidReferenceError if the SHA1 ref is not found
        in the repository. Raises an IOError if the requested file is not
        found in the ref.

        '''

        if not morphlib.git.is_valid_sha1(ref):
            raise UnresolvedNamedReferenceError(self, ref)
        try:
            sha1 = self._rev_list(ref).strip()
        except cliapp.AppException:
            raise InvalidReferenceError(self, ref)

        try:
            return self._cat_file(sha1, filename)
        except cliapp.AppException:
            raise IOError('File %s does not exist in ref %s of repo %s' %
                          (filename, ref, self))

    def clone_checkout(self, ref, target_dir):
        '''Clone from the cache into the target path and check out a given ref.

        Raises a CheckoutDirectoryExistsError if the target
        directory already exists. Raises an InvalidReferenceError if the
        ref is not found in the repository. Raises a CheckoutError if
        something else goes wrong while copying the repository or checking
        out the SHA1 ref.

        '''

        if os.path.exists(target_dir):
            raise CheckoutDirectoryExistsError(self, target_dir)

        self.resolve_ref(ref)

        self._clone_into(target_dir, ref)

    def checkout(self, ref, target_dir):
        '''Unpacks the repository in a directory and checks out a commit ref.

        Raises an InvalidReferenceError if the ref is not found in the
        repository. Raises a CopyError if something goes wrong with the copy
        of the repository. Raises a CheckoutError if something else goes wrong
        while copying the repository or checking out the SHA1 ref.

        '''

        if not os.path.exists(target_dir):
            os.mkdir(target_dir)

        # Note, we copy instead of cloning because it's much faster in the case
        # that the target is on a different filesystem from the cache. We then
        # take care to turn the copy into something as good as a real clone.
        self._copy_repository(self.path, target_dir)

        self._checkout_ref(ref, target_dir)

    def ls_tree(self, ref):
        '''Return file names found in root tree. Does not recurse to subtrees.

        Raises an UnresolvedNamedReferenceError if the ref is not a SHA1
        ref. Raises an InvalidReferenceError if the SHA1 ref is not found
        in the repository.

        '''

        if not morphlib.git.is_valid_sha1(ref):
            raise UnresolvedNamedReferenceError(self, ref)
        try:
            sha1 = self._rev_list(ref).strip()
        except cliapp.AppException:
            raise InvalidReferenceError(self, ref)

        return self._ls_tree(sha1)

    def update(self):
        '''Updates the cached repository using its origin remote.

        Raises an UpdateError if anything goes wrong while performing
        the update.

        '''

        try:
            self._update()
        except cliapp.AppException, e:
            raise UpdateError(self)

    def _runcmd(self, *args, **kwargs):  # pragma: no cover
        if not 'cwd' in kwargs:
            kwargs['cwd'] = self.path
        return self.app.runcmd(*args, **kwargs)

    def _show_ref(self, ref):  # pragma: no cover
        return self._runcmd(['git', 'show-ref', ref])

    def _show_tree_hash(self, absref):  # pragma: no cover
        return self._runcmd(
                ['git', 'log', '-1', '--format=format:%T', absref]).strip()

    def _rev_list(self, ref):  # pragma: no cover
        return self._runcmd(['git', 'rev-list', '--no-walk', ref])

    def _ls_tree(self, ref):  # pragma: no cover
        result = self._runcmd(['git', 'ls-tree', '--name-only', ref])
        return result.split('\n')

    def _cat_file(self, ref, filename):  # pragma: no cover
        return self._runcmd(['git', 'cat-file', 'blob',
                             '%s:%s' % (ref, filename)])

    def _clone_into(self, target_dir, ref):  #pragma: no cover
        '''Actually perform the clone'''
        try:
            morphlib.git.clone_into(self._runcmd, self.path, target_dir, ref)
        except cliapp.AppException:
            raise CloneError(self, target_dir)

    def _copy_repository(self, source_dir, target_dir):  # pragma: no cover
        try:
            morphlib.git.copy_repository(self._runcmd, source_dir, target_dir)
        except cliapp.AppException:
            raise CopyError(self, target_dir)

    def _checkout_ref(self, ref, target_dir):  # pragma: no cover
        try:
            morphlib.git.checkout_ref(self._runcmd, target_dir, ref)
        except cliapp.AppException:
            raise CheckoutError(self, ref, target_dir)

    def _update(self):  # pragma: no cover
        self._runcmd(['git', 'remote', 'update', 'origin', '--prune'])

    def __str__(self):  # pragma: no cover
        return self.url
