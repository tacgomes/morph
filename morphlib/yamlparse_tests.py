# Copyright (C) 2013-2015  Codethink Limited
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

import unittest

import morphlib
import morphlib.yamlparse as yamlparse
from morphlib.util import OrderedDict

if morphlib.got_yaml:
    yaml = morphlib.yaml


class YAMLParseTests(unittest.TestCase):

    def run(self, *args, **kwargs):
        if morphlib.got_yaml:
            return unittest.TestCase.run(self, *args, **kwargs)

    example_text = '''\
name: foo
kind: chunk
build-system: manual
'''

    example_dict = OrderedDict([
        ('name', 'foo'),
        ('kind', 'chunk'),
        ('build-system', 'manual'),
    ])

    def test_non_map_raises(self):
        incorrect_type = '''\
!!map
- foo
- bar
'''
        self.assertRaises(yaml.YAMLError, yamlparse.load, incorrect_type)

    def test_complex_key_fails_KNOWNFAILURE(self):
        complex_key = '? { foo: bar, baz: qux }: True'
        self.assertRaises(yaml.YAMLError, yamlparse.load, complex_key)

    def test_represents_non_scalar_nodes(self):
        self.assertTrue(
            yamlparse.dump(
                {
                    ('a', 'b'): {
                        "foo": 1,
                        "bar": 2,
                    }
                }, default_flow_style=None))
