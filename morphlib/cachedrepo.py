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

import morphlib.execute


class InvalidReferenceError(cliapp.AppException):

    def __init__(self, repo, ref):
        Exception.__init__(self, 'Ref %s is an invalid reference for repo %s' %
                           (ref, repo))


class UnresolvedNamedReferenceError(cliapp.AppException):

    def __init__(self, repo, ref):
        Exception.__init__(self, 'Ref %s is not a SHA1 ref for repo %s' %
                           (ref, repo))


class CheckoutDirectoryExistsError(cliapp.AppException):

    def __init__(self, repo, target_dir):
        Exception.__init__(
                self, 'Checkout directory %s for repo %s already exists' %
                (target_dir, repo))


class CheckoutError(cliapp.AppException):

    def __init__(self, repo, ref, target_dir):
        Exception.__init__(self, 'Failed to check out %s:%s into %s' %
                           (repo, ref, target_dir))


class UpdateError(cliapp.AppException):

    def __init__(self, repo):
        Exception.__init__(self, 'Failed to update cached version of repo %s' %
                           repo)


class CachedRepo(object):

    '''A locally cached Git repository with an origin remote set up.
    
    On instance of this class represents a locally cached version of a
    remote Git repository. This remote repository is set up as the
    'origin' remote.

    CachedRepo objects can resolve Git refs into SHA1s. Given a SHA1
    ref, they can also be asked to return the contents of a file via the
    cat() method. They can furthermore check out the repository into
    a local directory using a SHA1 ref. Last but not least, any cached
    repo may be updated from it's origin remote using the update()
    method.

    '''

    def __init__(self, url, path):
        '''Creates a new CachedRepo for a given repo URL and local path.'''

        self.url = url
        self.path = path
        self.ex = morphlib.execute.Execute(self.path, logging.debug)

    def is_valid_sha1(self, ref):
        '''Checks whether a string is a valid SHA1.'''

        valid_chars = 'abcdefABCDEF0123456789'
        return len(ref) == 40 and all([x in valid_chars for x in ref])

    def resolve_ref(self, ref):
        '''Attempts to resolve a Git ref into its corresponding SHA1.

        Raises an InvalidReferenceError if the ref is not found in the
        repository.

        '''

        try:
            refs = self._show_ref(ref).split('\n')
            # split each ref line into an array, drop non-origin branches
            refs = [x.split() for x in refs if 'origin' in x]
            return refs[0][0]
        except morphlib.execute.CommandFailure:
            pass

        if not self.is_valid_sha1(ref):
            raise InvalidReferenceError(self, ref)
        try:
            return self._rev_list(ref)
        except morphlib.execute.CommandFailure:
            raise InvalidReferenceError(self, ref)

    def cat(self, ref, filename):
        '''Attempts to read a file given a SHA1 ref.

        Raises an UnresolvedNamedReferenceError if the ref is not a SHA1
        ref. Raises an InvalidReferenceError if the SHA1 ref is not found
        in the repository. Raises an IOError if the requested file is not
        found in the ref.

        '''

        if not self.is_valid_sha1(ref):
            raise UnresolvedNamedReferenceError(self, ref)
        try:
            sha1 = self._rev_list(ref)
        except morphlib.execute.CommandFailure:
            raise InvalidReferenceError(self, ref)

        try:
            return self._cat_file(sha1, filename)
        except morphlib.execute.CommandFailure:
            raise IOError('File %s does not exist in ref %s of repo %s' %
                          (filename, ref, self))

    def checkout(self, ref, target_dir):
        '''Unpacks the repository in a directory and checks out a SHA1 ref.

        Raises an UnresolvedNamedReferenceError if the specified ref is not
        a SHA1 ref. Raises a CheckoutDirectoryExistsError if the target
        directory already exists. Raises an InvalidReferenceError if the
        ref is not found in the repository. Raises a CheckoutError if
        something else goes wrong while copying the repository or checking
        out the SHA1 ref.

        '''

        if not self.is_valid_sha1(ref):
            raise UnresolvedNamedReferenceError(self, ref)

        if os.path.exists(target_dir):
            raise CheckoutDirectoryExistsError(self, target_dir)
            
        os.mkdir(target_dir)

        try:
            sha1 = self._rev_list(ref)
        except morphlib.execute.CommandFailure:
            raise InvalidReferenceError(self, ref)
        
        try:
            self._copy_repository(self.path, target_dir)
            self._checkout_ref(sha1, target_dir)
        except morphlib.execute.CommandFailure:
            raise CheckoutError(self, ref, target_dir)

    def update(self):
        '''Updates the cached repository using its origin remote.
        
        Raises an UpdateError if anything goes wrong while performing
        the update.
        
        '''

        try:
            self._update()
        except morphlib.execute.CommandFailure:
            raise UpdateError(self)

    def _show_ref(self, ref): # pragma: no cover
        return self.ex.runv(['git', 'show-ref', ref])

    def _rev_list(self, ref): # pragma: no cover
        return self.ex.runv(['git', 'rev-list', '--no-walk', ref])

    def _cat_file(self, ref, filename): # pragma: no cover
        return self.ex.runv(['git', 'cat-file', 'blob',
                             '%s:%s' % (ref, filename)])

    def _copy_repository(self, source_dir, target_dir): # pragma: no cover
        self.ex.runv(['cp', '-a', os.path.join(source_dir, '.git'),
                      target_dir])

    def _checkout_ref(self, ref, target_dir): # pragma: no cover
        self.ex.runv(['git', 'checkout', ref], pwd=target_dir)

    def _update(self): # pragma: no cover
        self.ex.runv(['git', 'remote', 'update', 'origin'])

    def __str__(self): # pragma: no cover
        return self.url
