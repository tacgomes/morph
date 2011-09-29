# Copyright (C) 2011  Codethink Limited
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License.
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


class CacheDir(object):

    '''Manage Baserock cached binaries.'''
    
    def __init__(self, dirname):
        self.dirname = dirname
        
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

