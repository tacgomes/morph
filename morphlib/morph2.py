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


import json


class Morphology(object):

    '''An in-memory representation of a morphology.

    This is a parsed version of the morphology, with rules for default
    values applied. No other processing.

    '''

    static_defaults = [
        ('configure-commands', None),
        ('build-commands', None),
        ('test-commands', None),
        ('install-commands', None),
        ('chunks', []),
        ('strata', []),
        ('max-jobs', None),
        ('description', ''),
        ('build-depends', None),
        ('build-system', 'manual'),
        ('arch', None),
        ('system-kind', None),
    ]

    def __init__(self, text):
        self._dict = json.loads(text)
        self._set_defaults()
        self._create_child_index()

    def __getitem__(self, key):
        return self._dict[key]

    def __contains__(self, key):
        return key in self._dict

    def keys(self):
        return self._dict.keys()

    def lookup_morphology_by_name(self, name):
        '''Find child morphology by its morphology name, honouring aliases
        defined within this stratum.'''
        return self._child_dict[name]

    def _set_defaults(self):
        if 'max-jobs' in self:
            self._dict['max-jobs'] = int(self['max-jobs'])

        if 'disk-size' in self:
            size = self['disk-size']
            size = size.lower()
            if size.endswith('g'):
                size = int(size[:-1]) * 1024 ** 3
            elif size.endswith('m'):  # pragma: no cover
                size = int(size[:-1]) * 1024 ** 2
            elif size.endswith('k'):  # pragma: no cover
                size = int(size[:-1]) * 1024
            else:  # pragma: no cover
                size = int(size)
            self._dict['disk-size'] = size

        for name, value in self.static_defaults:
            if name not in self._dict:
                self._dict[name] = value

        if self['kind'] == 'stratum':
            self._set_stratum_defaults()

    def _set_stratum_defaults(self):
        for source in self['chunks']:
            if 'repo' not in source:
                source['repo'] = source['name']
            if 'morph' not in source:
                source['morph'] = source['name']
            if 'build-depends' not in source:
                source['build-depends'] = None

    def _get_valid_triple(self, info):
        return (info['repo'], info['ref'], "%s.morph" % info['morph'])

    def _create_child_index(self):
        self._child_dict = {}
        if self['kind'] == 'system':
            for info in self['strata']:
                source_name = info.get('alias', info['morph'])
                if source_name in self._child_dict:
                    raise ValueError("duplicate stratum name: " + source_name)
                self._child_dict[source_name] = self._get_valid_triple(info)
        elif self['kind'] == 'stratum':
            for info in self['chunks']:
                # FIXME: in the future, chunks will have an 'alias' field too
                source_name = info['name']
                if source_name in self._child_dict:
                    raise ValueError("duplicate chunk name: " + source_name)
                self._child_dict[source_name] = self._get_valid_triple(info)
