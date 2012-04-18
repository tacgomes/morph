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
import json
import urllib2
import urlparse


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


class RemoteRepoCache(object):

    def __init__(self, server_url, base_urls):
        self.server_url = server_url
        self._base_urls = base_urls

    def _base_iterate(self, repo_name):
        for base_url in self._base_urls:
            if not base_url.endswith('/'):
                base_url += '/'
            repo_url = urlparse.urljoin(base_url, repo_name)
            yield repo_url

    def resolve_ref(self, repo_name, ref):
        for repo_url in self._base_iterate(repo_name):
            try:
                return self._resolve_ref_for_repo_url(repo_url, ref)
            except:
                pass
        raise ResolveRefError(repo_name, ref)

    def cat_file(self, repo_name, ref, filename):
        for repo_url in self._base_iterate(repo_name):
            try:
                return self._cat_file_for_repo_url(repo_url, ref, filename)
            except:
                pass
        raise CatFileError(repo_name, ref, filename)

    def _resolve_ref_for_repo_url(self, repo_url, ref): # pragma: no cover
        data = self._make_request('sha1s?repo=%s&ref=%s' % (repo_url, ref))
        info = json.loads(data)
        return info['sha1']

    def _cat_file_for_repo_url(self, repo_url, ref,
                               filename): # pragma: no cover
        return self._make_request(
                'files?repo=%s&ref=%s&filename=%s' % (repo_url, ref, filename))

    def _make_request(self, path):
        server_url = self.server_url
        if not server_url.endswith('/'):
            server_url += '/'
        url = urlparse.urljoin(server_url, '/1.0/%s' % path)
        handle = urllib2.urlopen(url)
        return handle.read()
