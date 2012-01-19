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


class Blob(object):

    @staticmethod
    def create_blob(morph):
        if morph.kind == 'stratum':
            return Stratum(morph)
        elif morph.kind == 'chunk':
            return Chunk(morph)
        elif morph.kind == 'system':
            return System(morph)
        else:
            raise TypeError('Morphology %s has an unknown type: %s' % 
                            (morph.filename, morph.kind))

    def __init__(self, morph):
        self.parents = []
        self.morph = morph
        self.dependencies = []
        self.dependents = []

    def add_parent(self, parent):
        self.parents.append(parent)

    def remove_parent(self, parent):
        self.parents.remove(parent)

    def add_dependency(self, other):
        self.dependencies.append(other)
        other.dependents.append(self)

    def remove_dependency(self, other):
        self.dependencies.remove(other)
        other.dependents.remove(self)

    def depends_on(self, other):
        return other in self.dependencies

    @property
    def chunks(self):
        if self.morph.chunks:
            return self.morph.chunks
        else:
            return { self.morph.name: ['.'] }

    def __str__(self): # pragma: no cover
        return str(self.morph)


class Chunk(Blob):

    pass


class Stratum(Blob):

    pass


class System(Blob):

    pass
