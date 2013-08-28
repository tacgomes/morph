# Copyright (C) 2013  Codethink Limited
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
import unittest

import morphlib


def dummy_top_down_walker(root, treedict):
    '''Something that imitates os.walk, but with a dict'''

    subdirs = [k for k in treedict if isinstance(treedict[k], dict)]
    files = [k for k in treedict if not isinstance(treedict[k], dict)]
    yield root, subdirs, files
    for subdir in subdirs:
        subwalker = dummy_top_down_walker(os.path.join(root, subdir),
                                          treedict[subdir])
        for result in subwalker:
            yield result


class InvertPathsTests(unittest.TestCase):

    def setUp(self):
        self.flat_tree = {"foo": None, "bar": None, "baz": None}
        self.nested_tree = {
            "foo": {
                "bar": None,
                "baz": None,
            },
            "fs": {
                "btrfs": None,
                "ext2": None,
                "ext3": None,
                "ext4": None,
                "nfs": None,
            },
        }

    def test_flat_lists_single_files(self):
        walker = dummy_top_down_walker('.', self.flat_tree)
        self.assertEqual(sorted(["./foo", "./bar", "./baz"]),
                         sorted(morphlib.fsutils.invert_paths(walker, [])))

    def test_flat_excludes_listed_files(self):
        walker = dummy_top_down_walker('.', self.flat_tree)
        self.assertTrue(
            "./bar" not in morphlib.fsutils.invert_paths(walker, ["./bar"]))

    def test_nested_excludes_listed_files(self):
        walker = dummy_top_down_walker('.', self.nested_tree)
        excludes = ["./foo/bar", "./fs/nfs"]
        found = frozenset(morphlib.fsutils.invert_paths(walker, excludes))
        self.assertTrue(all(path not in found for path in excludes))

    def test_nested_excludes_whole_dir(self):
        walker = dummy_top_down_walker('.', self.nested_tree)
        found = frozenset(morphlib.fsutils.invert_paths(walker, ["./foo"]))
        unexpected = ("./foo", "./foo/bar", "./foo/baz")
        self.assertTrue(all(path not in found for path in unexpected))

    def test_lower_mount_precludes(self):
        walker = dummy_top_down_walker('.', {
            "tmp": {
                "morph": {
                    "staging": {
                        "build": None,
                        "inst": None,
                    },
                },
                "ccache": {
                    "0": None
                },
            },
            "bin": {
            },
        })
        found = frozenset(morphlib.fsutils.invert_paths(
            walker, [
                     "./tmp/morph/staging/build",
                     "./tmp/morph/staging/inst",
                     "./tmp",
                    ]))
        expected = ("./bin",)
        self.assertEqual(sorted(found), sorted(expected))
