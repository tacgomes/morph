# Copyright (C) 2012-2013  Codethink Limited
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
import json
import logging
import urllib2
import urlparse
import urllib


class ResolveRefError(cliapp.AppException):

    def __init__(self, repo_name, ref):
        cliapp.AppException.__init__(
            self, 'Failed to resolve ref %s for repo %s' %
            (ref, repo_name))


class CatFileError(cliapp.AppException):

    def __init__(self, repo_name, ref, filename):
        cliapp.AppException.__init__(
            self, 'Failed to cat file %s in ref %s of repo %s' %
            (filename, ref, repo_name))

class LsTreeError(cliapp.AppException):

    def __init__(self, repo_name, ref):
        cliapp.AppException.__init__(
            self, 'Failed to list tree in ref %s of repo %s' %
            (ref, repo_name))


class RemoteRepoCache(object):

    def __init__(self, server_url, resolver):
        self.server_url = server_url
        self._resolver = resolver

    def resolve_ref(self, repo_name, ref):
        repo_url = self._resolver.pull_url(repo_name)
        try:
            return self._resolve_ref_for_repo_url(repo_url, ref)
        except BaseException, e:
            logging.error('Caught exception: %s' % str(e))
            raise ResolveRefError(repo_name, ref)

    def cat_file(self, repo_name, ref, filename):
        repo_url = self._resolver.pull_url(repo_name)
        try:
            return self._cat_file_for_repo_url(repo_url, ref, filename)
        except BaseException, e:
            logging.error('Caught exception: %s' % str(e))
            raise CatFileError(repo_name, ref, filename)

    def ls_tree(self, repo_name, ref):
        repo_url = self._resolver.pull_url(repo_name)
        try:
            info = json.loads(self._ls_tree_for_repo_url(repo_url, ref))
            return info['tree'].keys()
        except BaseException, e:
            logging.error('Caught exception: %s' % str(e))
            raise LsTreeError(repo_name, ref)

    def _resolve_ref_for_repo_url(self, repo_url, ref):  # pragma: no cover
        data = self._make_request(
            'sha1s?repo=%s&ref=%s' % self._quote_strings(repo_url, ref))
        info = json.loads(data)
        return info['sha1'], info['tree']

    def _cat_file_for_repo_url(self, repo_url, ref,
                               filename):  # pragma: no cover
        return self._make_request(
            'files?repo=%s&ref=%s&filename=%s'
            % self._quote_strings(repo_url, ref, filename))

    def _ls_tree_for_repo_url(self, repo_url, ref):  # pragma: no cover
        return self._make_request(
            'trees?repo=%s&ref=%s' % self._quote_strings(repo_url, ref))

    def _quote_strings(self, *args):  # pragma: no cover
        return tuple(urllib.quote(string) for string in args)

    def _make_request(self, path):  # pragma: no cover
        server_url = self.server_url
        if not server_url.endswith('/'):
            server_url += '/'
        url = urlparse.urljoin(server_url, '/1.0/%s' % path)
        handle = urllib2.urlopen(url)
        return handle.read()
