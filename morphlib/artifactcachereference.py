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

class ArtifactCacheReference(object):

    '''Represent the information needed to retrieve an artifact

    The artifact cache doesn't need to know the dependencies or the
    morphology of an artifact, it just needs to know the cache key,
    name and kind.
    '''
    def __init__(self, name, cache_key, kind):
        self.name = name
        self.cache_key = cache_key
        self.kind = kind

    def basename(self):
        return '%s.%s.%s' % (self.cache_key,
                             self.kind,
                             self.name)

    def metadata_basename(self, metadata_name):
        return '%s.%s.%s.%s' % (self.cache_key,
                                self.kind,
                                self.name,
                                metadata_name)

    @classmethod
    def from_artifact(klass, artifact):
        return klass(artifact.name, artifact.cache_key,
                     artifact.source.morphology['kind'])
