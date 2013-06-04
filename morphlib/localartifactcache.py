# Copyright (C) 2012,2013  Codethink Limited
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
    '''Abstraction over the local artifact cache

       It provides methods for getting a file handle to cached artifacts
       so that the layout of the cache need not be known.

       It also updates modification times of artifacts so that it can track
       when they were last used, so it can be requested to clean up if
       disk space is low.

       Modification time is updated in both the get and has methods.

       NOTE: Parts of the build assume that every artifact of a source is
       available, so all the artifacts of a source need to be removed together.

       This complication needs to be handled either during the fetch logic, by
       updating the mtime of every artifact belonging to a source, or at
       cleanup time by only removing an artifact if every artifact belonging to
       a source is too old, and then remove them all at once.

       Since the cleanup logic will be complicated for other reasons it makes
       sense to put the complication there.
       '''

    def __init__(self, cachedir):
        self.cachedir = cachedir

    def put(self, artifact):
        filename = self.artifact_filename(artifact)
        return morphlib.savefile.SaveFile(filename, mode='w')

    def put_artifact_metadata(self, artifact, name):
        filename = self._artifact_metadata_filename(artifact, name)
        return morphlib.savefile.SaveFile(filename, mode='w')

    def put_source_metadata(self, source, cachekey, name):
        filename = self._source_metadata_filename(source, cachekey, name)
        return morphlib.savefile.SaveFile(filename, mode='w')

    def _has_file(self, filename):
        if os.path.exists(filename):
            os.utime(filename, None)
            return True
        return False

    def has(self, artifact):
        filename = self.artifact_filename(artifact)
        return self._has_file(filename)

    def has_artifact_metadata(self, artifact, name):
        filename = self._artifact_metadata_filename(artifact, name)
        return self._has_file(filename)

    def has_source_metadata(self, source, cachekey, name):
        filename = self._source_metadata_filename(source, cachekey, name)
        return self._has_file(filename)

    def get(self, artifact):
        filename = self.artifact_filename(artifact)
        os.utime(filename, None)
        return open(filename)

    def get_artifact_metadata(self, artifact, name):
        filename = self._artifact_metadata_filename(artifact, name)
        os.utime(filename, None)
        return open(filename)

    def get_source_metadata(self, source, cachekey, name):
        filename = self._source_metadata_filename(source, cachekey, name)
        os.utime(filename, None)
        return open(filename)

    def artifact_filename(self, artifact):
        basename = artifact.basename()
        return os.path.join(self.cachedir, basename)

    def _artifact_metadata_filename(self, artifact, name):
        basename = artifact.metadata_basename(name)
        return os.path.join(self.cachedir, basename)

    def _source_metadata_filename(self, source, cachekey, name):
        basename = '%s.%s' % (cachekey, name)
        return os.path.join(self.cachedir, basename)

    def clear(self):
        '''Clear everything from the artifact cache directory.
        
        After calling this, the artifact cache will be entirely empty.
        Caveat caller.
        
        '''

        for dirname, subdirs, basenames in os.walk(self.cachedir):
            for basename in basenames:
                os.remove(os.path.join(dirname, basename))

