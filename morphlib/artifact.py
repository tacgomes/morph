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


class Artifact(object):

    def __init__(self, source, name, cache_key):
        self.source = source
        self.name = name
        self.cache_key = cache_key
        self.dependencies = []
        self.dependents = []

    def add_dependency(self, artifact):
        '''Add ``artifact`` to the dependency list.'''
        if artifact not in self.dependencies:
            self.dependencies.append(artifact)
            artifact.dependents.append(self)

    def depends_on(self, artifact):
        '''Do we depend on ``artifact``?'''
        return artifact in self.dependencies

    def __str__(self): # pragma: no cover
        return '%s.%s.%s' % (self.cache_key,
                             self.source.morphology['kind'],
                             self.name)

