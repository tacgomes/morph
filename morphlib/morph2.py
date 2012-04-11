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
        ('configure-commands', []),
        ('build-commands', []),
        ('test-commands', []),
        ('install-commands', []),
        ('sources', []),
        ('strata', []),
        ('max-jobs', None),
        ('description', ''),
        ('build-depends', None),
        ('build-system', 'manual'),
    ]
    
    def __init__(self, text):
        self._dict = json.loads(text)
        self._set_defaults()
        
    def __getitem__(self, key):
        return self._dict[key]
        
    def __contains__(self, key):
        return key in self._dict
        
    def _set_defaults(self):
        if 'max-jobs' in self:
            self._dict['max-jobs'] = int(self['max-jobs'])

        if 'disk-size' in self:
            size = self['disk-size']
            size = size.lower()
            if size.endswith('g'):
                size = int(size[:-1]) * 1024**3
            elif size.endswith('m'): # pragma: no cover
                size = int(size[:-1]) * 1024**2
            elif size.endswith('k'): # pragma: no cover
                size = int(size[:-1]) * 1024
            else: # pragma: no cover
                size = int(size)
            self._dict['disk-size'] = size
    
        for name, value in self.static_defaults:
            if name not in self._dict:
                self._dict[name] = value

        if self['kind'] == 'stratum':
            self._set_stratum_defaults()
            
    def _set_stratum_defaults(self):
        for source in self['sources']:
            if 'repo' not in source:
                source['repo'] = source['name']
            if 'morph' not in source:
                source['morph'] = source['name']
            if 'build-depends' not in source:
                source['build-depends'] = None

