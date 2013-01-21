# Copyright (C) 2012-2013  Codethink Limited
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


import copy
import re

# It is intentional that if collections does not have OrderedDict that
# simplejson is also used in preference to json, as OrderedDict became
# a member of collections in the same release json got its object_pairs_hook
try: # pragma: no cover
    from collections import OrderedDict
    import json
except ImportError: # pragma: no cover
    from ordereddict import OrderedDict
    import simplejson as json


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
        self._dict = json.loads(text, object_pairs_hook=OrderedDict)
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
                source_name = info.get('alias', info['morph'])
                if source_name == name:
                    return info
        raise KeyError('"%s" not found' % name)

    def _set_defaults(self):
        if 'max-jobs' in self:
            self._dict['max-jobs'] = int(self['max-jobs'])

        if 'disk-size' in self:
            size = self['disk-size']
            self._dict['_disk-size'] = size
            self._dict['disk-size'] = self._parse_size(size)

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

    def _parse_size(self, size):
        if isinstance(size, basestring):
            size = size.lower()
            if size.endswith('g'):
                return int(size[:-1]) * 1024 ** 3
            elif size.endswith('m'):  # pragma: no cover
                return int(size[:-1]) * 1024 ** 2
            elif size.endswith('k'):  # pragma: no cover
                return int(size[:-1]) * 1024
        return int(size) # pragma: no cover

    def write_to_file(self, f): # pragma: no cover
        # Recreate dict without the empty default values, with a few kind
        # specific hacks to try and edit standard morphologies as
        # non-destructively as possible
        as_dict = OrderedDict()
        for key in self.keys():
            if self['kind'] == 'stratum' and key == 'chunks':
                value = copy.copy(self[key])
                for chunk in value:
                    if chunk["morph"] == chunk["name"]:
                        del chunk["morph"]
            if self['kind'] == 'system' and key == 'disk-size':
                # Use human-readable value (assumes we never programmatically
                # change this value within morph)
                value = self['_disk-size']
            else:
                value = self[key]
            if value and key[0] != '_':
                as_dict[key] = value
        text = json.dumps(as_dict, indent=4)
        text = re.sub(" \n", "\n", text)
        f.write(text)
        f.write('\n')
