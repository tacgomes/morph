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


import os
import shutil
import tempfile
import unittest

import morphlib


class CacheDirTests(unittest.TestCase):

    def cat(self, relative_name):
        with open(os.path.join(self.cachedir.dirname, relative_name)) as f:
            return f.read()

    def setUp(self):
        self.dirname = tempfile.mkdtemp()
        self.cachedir = morphlib.cachedir.CacheDir(self.dirname)

    def tearDown(self):
        shutil.rmtree(self.dirname)

    def test_sets_dirname_attribute(self):
        self.assertEqual(self.cachedir.dirname, os.path.abspath(self.dirname))

    def test_generates_string_key_for_arbitrary_dict_key(self):
        key = self.cachedir.key({
            'foo': 'bar',
            'xyzzy': 'plugh',
        })
        self.assertEqual(type(key), str)
        self.assertNotEqual(key, '')

    def test_generates_same_string_key_twice(self):
        dict_key = {
            'foo': 'bar',
            'xyzzy': 'plugh',
        }
        self.assertEqual(self.cachedir.key(dict_key),
                         self.cachedir.key(dict_key))

    def test_generates_different_string_keys(self):
        dict_key_1 = {
            'foo': 'bar',
            'xyzzy': 'plugh',
        }
        dict_key_2 = {
            'foo': 'foobar',
            'xyzzy': 'stevenage',
        }
        self.assertNotEqual(self.cachedir.key(dict_key_1),
                            self.cachedir.key(dict_key_2))

    def test_returns_a_chunk_pathname_in_cache_directory(self):
        dict_key = {
            'kind': 'chunk',
            'ref': 'DEADBEEF',
            'repo': 'git://git.baserock.org/hello/',
            'arch': 'armel',
        }
        pathname = self.cachedir.name(dict_key)
        self.assert_(pathname.startswith(self.cachedir.dirname + '/'))
        self.assert_(pathname.endswith('.chunk'))

    def test_returns_a_stratum_pathname_in_cache_directory(self):
        dict_key = {
            'kind': 'stratum',
            'ref': 'DEADBEEF',
            'repo': 'git://git.baserock.org/hello/',
            'arch': 'armel',
        }
        pathname = self.cachedir.name(dict_key)
        self.assert_(pathname.startswith(self.cachedir.dirname + '/'))
        self.assert_(pathname.endswith('.stratum'))

    def test_returns_a_valid_pathname_in_cache_directory(self):
        dict_key = {
            'ref': 'DEADBEEF',
            'repo': 'git://git.baserock.org/hello/',
            'arch': 'armel',
        }
        pathname = self.cachedir.name(dict_key)
        self.assert_(pathname.startswith(self.cachedir.dirname + '/'))

    def test_allows_file_to_be_written_via_basename(self):
        f = self.cachedir.open('foo')
        f.write('bar')
        f.close()
        self.assertEqual(self.cat('foo'), 'bar')

    def test_allows_file_to_be_written_via_basename_and_suffix(self):
        f = self.cachedir.open('foo', '.blip')
        f.write('bar')
        f.close()
        self.assertEqual(self.cat('foo.blip'), 'bar')

    def test_allows_file_to_be_written_via_dict_key(self):
        dict_key = {
            'kind': 'chunk',
            'meh': 'moo',
        }
        name = self.cachedir.name(dict_key)
        f = self.cachedir.open(dict_key)
        f.write('bar')
        f.close()
        self.assertEqual(self.cat(name), 'bar')

    def test_allows_file_to_be_aborted(self):
        f = self.cachedir.open('foo')
        f.write('bar')
        f.abort()
        pathname = os.path.join(self.cachedir.dirname, 'foo')
        self.assertFalse(os.path.exists(pathname))
