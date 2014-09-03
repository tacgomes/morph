# Copyright (C) 2012-2014  Codethink Limited
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


import collections


class SourcePool(object):

    '''Manage a collection of Source objects.'''

    def __init__(self):
        self._sources = collections.defaultdict(dict)
        self._order = []

    def _key(self, repo_name, original_ref, filename):
        return (repo_name, original_ref, filename)

    def add(self, source):
        '''Add a source to the pool.'''
        key = self._key(source.repo_name,
                        source.original_ref,
                        source.filename)
        if key not in self._sources or source.name not in self._sources[key]:
            self._sources[key][source.name] = source
            self._order.append(source)

    def lookup(self, repo_name, original_ref, filename):
        '''Find a source in the pool.

        Raise KeyError if it is not found.

        '''

        key = self._key(repo_name, original_ref, filename)
        return self._sources[key].values()

    def __iter__(self):
        '''Iterate over sources in the pool, in the order they were added.'''
        for source in self._order:
            yield source

    def __len__(self):
        return len(self._sources)
