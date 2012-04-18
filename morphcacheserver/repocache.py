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
import os
import string


class RepositoryNotFoundError(cliapp.AppException):

    def __init__(self, repo):
        cliapp.AppException.__init__(
                self, 'Repository %s does not exist in the cache' % repo)


class InvalidReferenceError(cliapp.AppException):
    
    def __init__(self, repo, ref):
        cliapp.AppException.__init__(
                self, 'Ref %s is an invalid reference for repo %s' %
                (ref, repo))


class UnresolvedNamedReferenceError(cliapp.AppException):

    def __init__(self, repo, ref):
        cliapp.AppException.__init__(
                self, 'Ref %s is not a SHA1 ref for repo %s' %
                (ref, repo))


class RepoCache(object):
    
    def __init__(self, app, repo_cache_dir, bundle_cache_dir):
        self.app = app
        self.repo_cache_dir = repo_cache_dir
        self.bundle_cache_dir = bundle_cache_dir

    def resolve_ref(self, repo_url, ref):
        quoted_url = self._quote_url(repo_url)
        repo_dir = os.path.join(self.repo_cache_dir, quoted_url)
        if not os.path.exists(repo_dir):
            raise RepositoryNotFoundError(repo_url)
        try:
            refs = self._show_ref(repo_dir, ref).split('\n')
            refs = [x.split() for x in refs if 'origin' in x]
            return refs[0][0]
        except cliapp.AppException:
            pass
        if not self._is_valid_sha1(ref):
            raise InvalidReferenceError(repo_url, ref)
        try:
            return self._rev_list(ref).strip()
        except:
            raise InvalidReferenceError(repo_url, ref)

    def cat_file(self, repo_url, ref, filename):
        quoted_url = self._quote_url(repo_url)
        repo_dir = os.path.join(self.repo_cache_dir, quoted_url)
        if not self._is_valid_sha1(ref):
            raise UnresolvedNamedReferenceError(repo_url, ref)
        if not os.path.exists(repo_dir):
            raise RepositoryNotFoundError(repo_url)
        try:
            sha1 = self._rev_list(repo_dir, ref).strip()
        except:
            raise InvalidReferenceError(repo_url, ref)

        return self._cat_file(repo_dir, sha1, filename)

    def get_bundle_filename(self, repo_url):
        quoted_url = self._quote_url(repo_url)
        return os.path.join(self.bundle_dir, '%s.bndl' % quoted_url)
        
    def _quote_url(self, url):
        valid_chars = string.digits + string.letters + '%_'
        transl = lambda x: x if x in valid_chars else '_'
        return ''.join([transl(x) for x in url])

    def _show_ref(self, repo_dir, ref):
        return self.app.runcmd(['git', 'show-ref', ref], cwd=repo_dir)

    def _rev_list(self, repo_dir, ref):
        return self.app.runcmd(
                ['git', 'rev-list', '--no-walk', ref], cwd=repo_dir)

    def _cat_file(self, repo_dir, sha1, filename):
        return self.app.runcmd(
                ['git', 'cat-file', 'blob', '%s:%s' % (sha1, filename)],
                cwd=repo_dir)

    def _is_valid_sha1(self, ref):
        valid_chars = 'abcdefABCDEF0123456789'
        return len(ref) == 40 and all([x in valid_chars for x in ref])
