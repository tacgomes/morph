# Copyright (C) 2011-2012  Codethink Limited
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


import hashlib
import os


class CacheDir(object):

    '''Manage Baserock cached binaries.'''
    
    def __init__(self, dirname):
        self.dirname = os.path.abspath(dirname)
        
    def key(self, dict_key):
        '''Create a string key from a dictionary key.
        
        The string key can be used as a filename, or as part of one.
        The dictionary key is a dict that maps any set of strings to
        another set of strings.
        
        The same string key is guaranteed to be returned for a given
        dictionary key. It is highly unlikely that two different dictionary
        keys result in the same string key.
        
        '''
        
        data = ''.join(key + value for key, value in dict_key.iteritems())
        return hashlib.sha256(data).hexdigest()

    def name(self, dict_key):
        '''Return a filename for an object described by dictionary key.
        
        It is the caller's responsibility to set the fields in the
        dictionary key suitably. For example, if there is a field
        specifying a commit id, it should be the full git SHA-1
        identifier, not something ephemeral like HEAD.
        
        If the field 'kind' has a value, it is used as a suffix for
        the filename.
        
        '''

        key = self.key(dict_key)
        if 'kind' in dict_key and dict_key['kind']:
            suffix = '.%s' % dict_key['kind']
        else:
            suffix = ''

        return os.path.join(self.dirname, key + suffix)

