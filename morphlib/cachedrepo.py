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
        Exception.__init__(self, '%s is an invalid reference for repo %s' %
                           (ref, repo))


class UnresolvedNamedReferenceError(cliapp.AppException):

    def __init__(self, repo, ref):
        Exception.__init__(self, '%s is not a SHA1 ref for repo %s' %
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

    def __init__(self, url, path):
        self.url = url
        self.path = path
        self.ex = morphlib.execute.Execute(self.path, logging.debug)

    def is_valid_sha1(self, ref):
        valid_chars = 'abcdefABCDEF0123456789'
        return len(ref) == 40 and all([x in valid_chars for x in ref])

    def resolve_ref(self, ref):
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
