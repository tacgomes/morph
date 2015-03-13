# Copyright (C) 2013,2015  Codethink Limited
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
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# =*= License: GPL-2 =*=


import operator
import os
import shutil
import tempfile
import unittest

import morphlib


class SystemMetadataDirTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.metadatadir = os.path.join(self.tempdir, 'baserock')
        os.mkdir(self.metadatadir)
        self.smd = morphlib.systemmetadatadir.SystemMetadataDir(
            self.metadatadir)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_add_new(self):
        self.smd['key'] = {'foo': 'bar'}
        self.assertEqual(self.smd['key']['foo'], 'bar')

    def test_replace(self):
        self.smd['key'] = {'foo': 'bar'}
        self.smd['key'] = {'foo': 'baz'}
        self.assertEqual(self.smd['key']['foo'], 'baz')

    def test_remove(self):
        self.smd['key'] = {'foo': 'bar'}
        del self.smd['key']
        self.assertTrue('key' not in self.smd)

    def test_iterate(self):
        self.smd['build-essential'] = "Some data"
        self.smd['core'] = "More data"
        self.smd['foundation'] = "Yet more data"
        self.assertEqual(sorted(self.smd.keys()),
                         ['build-essential', 'core', 'foundation'])
        self.assertEqual(dict(self.smd.iteritems()),
                         {
                             'build-essential': "Some data",
                             'core': "More data",
                             'foundation': "Yet more data",
                         })

    def test_raises_KeyError(self):
        self.assertRaises(KeyError, operator.getitem, self.smd, 'key')

    def test_validates_keys(self):
        for key in ('foo/bar', 'baz\0quux'):
            self.assertRaises(KeyError, operator.getitem, self.smd, key)
            self.assertRaises(KeyError, operator.setitem,
                              self.smd, key, 'value')
            self.assertRaises(KeyError, operator.delitem, self.smd, key)
