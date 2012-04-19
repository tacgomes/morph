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
import httplib2
import urllib2
import urlparse


class GetError(cliapp.AppException):

    def __init__(self, cache, artifact):
        cliapp.AppException.__init__(
                self, 'Failed to get the artifact %s from the '
                'artifact cache %s' % (artifact, cache))


class GetArtifactMetadataError(cliapp.AppException):

    def __init__(self, cache, artifact, name):
        cliapp.AppException.__init__(
                self, 'Failed to get metadata %s for the artifact %s '
                'from the artifact cache %s' % (name, artifact, cache))


class GetSourceMetadataError(cliapp.AppException):

    def __init__(self, cache, source, cache_key, name):
        cliapp.AppException.__init__(
                self, 'Failed to get metadata %s for source %s '
                'and cache key %s from the artifact cache %s' %
                (name, source, cache_key, cache))


class RemoteArtifactCache(object):

    def __init__(self, server_url):
        self.server_url = server_url

    def has(self, artifact):
        return self._has_file(artifact.basename())

    def has_artifact_metadata(self, artifact, name):
        return self._has_file(artifact.metadata_basename(name))

    def has_source_metadata(self, source, cachekey, name):
        filename = '%s.%s' % (cachekey, name)
        return self._has_file(filename)

    def get(self, artifact):
        try:
            return self._get_file(artifact.basename())
        except:
            raise GetError(self, artifact)

    def get_artifact_metadata(self, artifact, name):
        try:
            return self._get_file(artifact.metadata_basename(name))
        except:
            raise GetArtifactMetadataError(self, artifact, name)

    def get_source_metadata(self, source, cachekey, name):
        filename = '%s.%s' % (cachekey, name)
        try:
            return self._get_file(filename)
        except:
            raise GetSourceMetadataError(self, source, cachekey, name)

    def _has_file(self, filename): # pragma: no cover
        url = self._request_url(filename)
        http = httplib2.Http()
        response = http.request(url, 'HEAD')
        status = response[0]['status']
        return status >= 200 and status < 400

    def _get_file(self, filename): # pragma: no cover
        url = self._request_url(filename)
        return urllib2.urlopen(url)

    def _request_url(self, filename): # pragma: no cover
        server_url = self.server_url
        if not server_url.endswith('/'):
            server_url += '/'
        return urlparse.urljoin(
                server_url, '/1.0/artifacts/filename=%s' % filename)
