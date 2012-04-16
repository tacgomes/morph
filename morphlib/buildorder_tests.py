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


import unittest

import morphlib


class FakeSource(object):
    pass


class BuildOrderTests(unittest.TestCase):

    def test_empty_list_results_in_no_groups_at_all(self):
        order = morphlib.buildorder.BuildOrder([])
        self.assertEqual(len(order.groups), 0)

    def test_list_with_one_artifact_results_in_one_group(self):
        chunk = FakeSource()
        artifact = morphlib.artifact.Artifact(chunk, 'chunk', 'key')

        order = morphlib.buildorder.BuildOrder([artifact])

        self.assertEqual(len(order.groups), 1)
        self.assertEqual(order.groups[0], [artifact])

    def test_list_with_two_unrelated_artifacts_results_in_one_group(self):
        chunk1 = FakeSource()
        artifact1 = morphlib.artifact.Artifact(chunk1, 'chunk1', 'key1')

        chunk2 = FakeSource()
        artifact2 = morphlib.artifact.Artifact(chunk2, 'chunk2', 'key2')

        order = morphlib.buildorder.BuildOrder([artifact1, artifact2])

        self.assertEqual(len(order.groups), 1)
        self.assertEqual(order.groups[0], [artifact1, artifact2])

    def test_list_with_two_dependent_artifacts_results_in_two_groups(self):
        chunk1 = FakeSource()
        artifact1 = morphlib.artifact.Artifact(chunk1, 'chunk1', 'key1')

        chunk2 = FakeSource()
        artifact2 = morphlib.artifact.Artifact(chunk2, 'chunk2', 'key2')
        artifact2.add_dependency(artifact1)

        order = morphlib.buildorder.BuildOrder([artifact1, artifact2])

        self.assertEqual(len(order.groups), 2)
        self.assertEqual(order.groups[0], [artifact1])
        self.assertEqual(order.groups[1], [artifact2])

    def test_chain_of_three_dependent_artifacts_results_in_three_groups(self):
        chunk1 = FakeSource()
        artifact1 = morphlib.artifact.Artifact(chunk1, 'chunk1', 'key1')

        chunk2 = FakeSource()
        artifact2 = morphlib.artifact.Artifact(chunk2, 'chunk2', 'key2')
        artifact2.add_dependency(artifact1)

        chunk3 = FakeSource()
        artifact3 = morphlib.artifact.Artifact(chunk3, 'chunk3', 'key3')
        artifact3.add_dependency(artifact2)

        order = morphlib.buildorder.BuildOrder(
                [artifact1, artifact2, artifact3])

        self.assertEqual(len(order.groups), 3)
        self.assertEqual(order.groups[0], [artifact1])
        self.assertEqual(order.groups[1], [artifact2])
        self.assertEqual(order.groups[2], [artifact3])

    def test_two_artifacts_depending_on_another_results_in_two_groups(self):
        chunk1 = FakeSource()
        artifact1 = morphlib.artifact.Artifact(chunk1, 'chunk1', 'key1')

        chunk2 = FakeSource()
        artifact2 = morphlib.artifact.Artifact(chunk2, 'chunk2', 'key2')
        artifact2.add_dependency(artifact1)

        chunk3 = FakeSource()
        artifact3 = morphlib.artifact.Artifact(chunk3, 'chunk3', 'key3')
        artifact3.add_dependency(artifact1)

        order = morphlib.buildorder.BuildOrder(
                [artifact1, artifact2, artifact3])

        self.assertEqual(len(order.groups), 2)
        self.assertEqual(order.groups[0], [artifact1])
        self.assertEqual(order.groups[1], [artifact2, artifact3])

    def test_one_artifact_depending_on_two_others_results_in_two_groups(self):
        chunk1 = FakeSource()
        artifact1 = morphlib.artifact.Artifact(chunk1, 'chunk1', 'key1')

        chunk2 = FakeSource()
        artifact2 = morphlib.artifact.Artifact(chunk2, 'chunk2', 'key2')

        chunk3 = FakeSource()
        artifact3 = morphlib.artifact.Artifact(chunk3, 'chunk3', 'key3')
        artifact3.add_dependency(artifact1)
        artifact3.add_dependency(artifact2)

        order = morphlib.buildorder.BuildOrder(
                [artifact1, artifact2, artifact3])

        self.assertEqual(len(order.groups), 2)
        self.assertEqual(order.groups[0], [artifact1, artifact2])
        self.assertEqual(order.groups[1], [artifact3])

    def test_detection_of_cyclic_dependency_chain(self):
        chunk1 = FakeSource()
        artifact1 = morphlib.artifact.Artifact(chunk1, 'chunk1', 'key1')

        chunk2 = FakeSource()
        artifact2 = morphlib.artifact.Artifact(chunk2, 'chunk2', 'key2')

        chunk3 = FakeSource()
        artifact3 = morphlib.artifact.Artifact(chunk3, 'chunk3', 'key3')

        artifact1.add_dependency(artifact3)
        artifact2.add_dependency(artifact1)
        artifact3.add_dependency(artifact2)

        self.assertRaises(morphlib.buildorder.CyclicDependencyChainError,
                          morphlib.buildorder.BuildOrder,
                          [artifact1, artifact2, artifact3])
