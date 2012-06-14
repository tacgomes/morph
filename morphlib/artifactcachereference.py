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
    morphology of an artifact, it just needs to know the basename

    The basename could be generated, from the name, cache_key and kind,
    but if the algorithm changes then morph wouldn't be able to find
    old artifacts with a saved ArtifactCacheReference.

    Conversely if it generated the basename then old strata wouldn't be
    able to refer to new chunks, but strata change more often than the chunks.
    '''
    def __init__(self, basename):
        self._basename = basename

    def basename(self):
        return self._basename

    def metadata_basename(self, metadata_name):
        return '%s.%s' % (self._basename, metadata_name)
