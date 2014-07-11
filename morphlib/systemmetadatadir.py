# Copyright (C) 2013-2014  Codethink Limited
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
#
# =*= License: GPL-2 =*=


import collections
import glob
import json
import os


class SystemMetadataDir(collections.MutableMapping):

    '''An abstraction over the /baserock metadata directory.

    This allows methods of iterating over it, and accessing it like
    a dict.

    The /baserock metadata directory contains information about all of
    the chunks in a built system. It exists to provide traceability from
    the input sources to the output.

    If you create the object with smd = SystemMetadataDir('/baserock')
    data = smd['key'] will read /baserock/key.meta and return its JSON
    encoded contents as native python objects.

    smd['key'] = data will write data to /baserock/key.meta as JSON

    The key may not have '\0' characters in it since the underlying
    system calls don't support embedded NUL bytes.

    The key may not have '/' characters in it since we do not support
    morphologies with slashes in their names.

    '''

    def __init__(self, metadata_path):
        collections.MutableMapping.__init__(self)
        self._metadata_path = metadata_path

    def _join_path(self, *args):
        return os.path.join(self._metadata_path, *args)

    def _raw_path_iter(self):
        return glob.iglob(self._join_path('*.meta'))

    @staticmethod
    def _check_key(key):
        if any(c in key for c in "\0/"):
            raise KeyError(key)

    def __getitem__(self, key):
        self._check_key(key)
        try:
            with open(self._join_path('%s.meta' % key), 'r') as f:
                return json.load(f, encoding='unicode-escape')
        except IOError:
            raise KeyError(key)

    def __setitem__(self, key, value):
        self._check_key(key)
        with open(self._join_path('%s.meta' % key), 'w') as f:
            json.dump(value, f, indent=4, sort_keys=True,
                      encoding='unicode-escape')

    def __delitem__(self, key):
        self._check_key(key)
        os.unlink(self._join_path('%s.meta' % key))

    def __iter__(self):
        return (os.path.basename(fn)[:-len('.meta')]
                for fn in self._raw_path_iter())

    def __len__(self):
        return len(list(self._raw_path_iter()))
