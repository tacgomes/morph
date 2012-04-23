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


import hashlib
import logging

import morphlib


class CacheKeyComputer(object):

    def __init__(self, build_env):
        self._build_env = build_env
        self._calculated = {}

    def _filterenv(self, env):
        return dict([(k, env[k]) for k in ("USER", "USERNAME", "LOGNAME",
                                           "TOOLCHAIN_TARGET", "PREFIX",
                                           "BOOTSTRAP", "CFLAGS")])

    def compute_key(self, artifact):
        logging.debug('computing cache key for artifact %s from source '
                      'repo %s, sha1 %s, filename %s' %
                        (artifact.name, artifact.source.repo_name,
                         artifact.source.sha1, artifact.source.filename))
        return self._hash_id(self.get_cache_id(artifact))

    def _hash_id(self, cache_id):
        sha = hashlib.sha256()
        self._hash_dict(sha, cache_id)
        return sha.hexdigest()

    def _hash_thing(self, sha, thing):
        if type(thing) == dict:
            self._hash_dict(sha, thing)
        elif type(thing) == list:
            self._hash_list(sha, thing)
        elif type(thing) == tuple:
            self._hash_tuple(sha, thing)
        else:
            sha.update(str(thing))

    def _hash_dict(self, sha, d):
        for tup in sorted(d.iteritems()):
            self._hash_thing(sha, tup)

    def _hash_list(self, sha, l):
        for item in l:
            self._hash_thing(sha, item)

    def _hash_tuple(self, sha, tup):
        for item in tup:
            self._hash_thing(sha, item)

    def get_cache_id(self, artifact):
        try:
            return self._calculated[artifact]
        except KeyError:
            cacheid = self._calculate(artifact)
            self._calculated[artifact] = cacheid
            return cacheid

    def _calculate(self, artifact):
        return {
            'arch': self._build_env.arch,
            'env': self._filterenv(self._build_env.env),
            'ref': artifact.source.sha1,
            'filename': artifact.source.filename,
            'kids': [self.get_cache_id(x) for x in artifact.dependencies]
        }
