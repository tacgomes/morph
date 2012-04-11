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

import morphlib


class LocalArtifactCache(object):

    def __init__(self, cachedir):
        self.cachedir = cachedir

    def put(self, artifact):
        filename = self._artifact_filename(artifact)
        return morphlib.savefile.SaveFile(filename, mode='w')

    def put_artifact_metadata(self, artifact, name):
        filename = self._artifact_metadata_filename(artifact, name)
        return morphlib.savefile.SaveFile(filename, mode='w')

    def put_source_metadata(self, source, cachekey, name):
        filename = self._source_metadata_filename(source, cachekey, name)
        return morphlib.savefile.SaveFile(filename, mode='w')

    def has(self, artifact):
        filename = self._artifact_filename(artifact)
        return os.path.exists(filename)

    def has_artifact_metadata(self, artifact, name):
        filename = self._artifact_metadata_filename(artifact, name)
        return os.path.exists(filename)

    def has_source_metadata(self, source, cachekey, name):
        filename = self._source_metadata_filename(source, cachekey, name)
        return os.path.exists(filename)

    def get(self, artifact):
        filename = self._artifact_filename(artifact)
        return open(filename)

    def get_artifact_metadata(self, artifact, name):
        filename = self._artifact_metadata_filename(artifact, name)
        return open(filename)

    def get_source_metadata(self, source, cachekey, name):
        filename = self._source_metadata_filename(source, cachekey, name)
        return open(filename)

    def _artifact_basename(self, artifact):
        return '%s.%s.%s' % (artifact.cache_key,
                             artifact.source.morphology['kind'],
                             artifact.name)

    def _artifact_filename(self, artifact):
        basename = self._artifact_basename(artifact)
        return os.path.join(self.cachedir, basename)

    def _artifact_metadata_filename(self, artifact, name):
        basename = '%s.%s' % (self._artifact_basename(artifact), name)
        return os.path.join(self.cachedir, basename)


    def _source_metadata_filename(self, source, cachekey, name):
        basename = '%s.%s' % (cachekey, name)
        return os.path.join(self.cachedir, basename)
