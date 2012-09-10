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

    static_defaults = {
        'chunk': [
            ('description', ''),
            ('configure-commands', None),
            ('build-commands', None),
            ('test-commands', None),
            ('install-commands', None),
            ('chunks', []),
            ('max-jobs', None),
            ('build-system', 'manual')
        ],
        'stratum': [
            ('chunks', []),
            ('description', ''),
            ('build-depends', None)
        ],
        'system': [
            ('strata', []),
            ('description', ''),
            ('arch', None),
            ('system-kind', None)
        ]
    }

    def __init__(self, text):
        self._dict = json.loads(text)
        self._set_defaults()
        self._validate_children()

    def __getitem__(self, key):
        return self._dict[key]

    def __contains__(self, key):
        return key in self._dict

    def keys(self):
        return self._dict.keys()

    def _validate_children(self):
        if self['kind'] == 'system':
            names = set()
            for info in self['strata']:
                name = info.get('alias', info['morph'])
                if name in names:
                   raise ValueError('Duplicate stratum "%s"' % name)
                names.add(name)
        elif self['kind'] == 'stratum':
            names = set()
            for info in self['chunks']:
                name = info.get('alias', info['name'])
                if name in names:
                   raise ValueError('Duplicate chunk "%s"' % name)
                names.add(name)

    def lookup_child_by_name(self, name):
        '''Find child reference by its name.

        This lookup honors aliases.

        '''

        if self['kind'] == 'system':
            for info in self['strata']:
                source_name = info.get('alias', info['morph'])
                if source_name == name:
                    return info
        elif self['kind'] == 'stratum':
            for info in self['chunks']:
                source_name = info.get('alias', info['name'])
                if source_name == name:
                    return info
        raise KeyError('"%s" not found' % name)

    def _set_defaults(self):
        if 'max-jobs' in self:
            self._dict['max-jobs'] = int(self['max-jobs'])

        if 'disk-size' in self:
            size = self['disk-size']
            if isinstance(size, basestring):
                size = size.lower()
                if size.endswith('g'):
                    size = int(size[:-1]) * 1024 ** 3
                elif size.endswith('m'):  # pragma: no cover
                    size = int(size[:-1]) * 1024 ** 2
                elif size.endswith('k'):  # pragma: no cover
                    size = int(size[:-1]) * 1024
                else:  # pragma: no cover
                    size = int(size)
            else: # pragma: no cover
                size = int(size)
            self._dict['disk-size'] = size

        for name, value in self.static_defaults[self['kind']]:
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
