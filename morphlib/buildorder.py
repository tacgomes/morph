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


import cliapp
import collections


class CyclicDependencyChainError(cliapp.AppException):

    def __init__(self):
        cliapp.AppException.__init__(
            self, 'Cyclic dependency chain detected')


class BuildOrder:

    def __init__(self, artifacts):
        self.artifacts = artifacts

        if artifacts:
            sorting = self._compute_reverse_topological_sorting(artifacts)
            self.groups = self._create_build_groups(sorting)
        else:
            self.groups = []

    def _compute_reverse_topological_sorting(self, artifacts):
        '''Computes a reverse topological sorting of the build graph.

        A reverse topological sorting basically is the result of a series of
        breadth-first searches starting at each leaf node (artifacts with no
        dependents). Artifacts are added to the sorting as soon as all their
        dependents have been added.

        For more information, see
        http://en.wikipedia.org/wiki/Topological_sorting.

        '''

        # map artifacts to sets of satisfied dependents. this is to detect
        # when we can actually add artifacts to the BFS queue. rather than
        # dropping links between nodes, like most topological sorting
        # algorithms do, we simply remember all satisfied dependents and
        # check if all of them are met repeatedly
        satisfied_dependents = {}

        # create an empty sorting
        sorting = collections.deque()

        # create a set of leafs to start the DFS from
        leafs = collections.deque()
        for artifact in artifacts:
            satisfied_dependents[artifact] = set()
            if len(artifact.dependents) == 0:
                leafs.append(artifact)

        while len(leafs) > 0:
            # fetch a leaf artifact from the DFS queue
            artifact = leafs.popleft()

            # add it to the sorting
            sorting.append(artifact)

            # mark this dependency as resolved in dependent artifacts
            for dependency in artifact.dependencies:
                satisfied_dependents[dependency].add(artifact)

                # add the dependent blob as a leaf if all
                # its dependents have been resolved
                has = len(satisfied_dependents[dependency])
                needs = len(dependency.dependents)
                if has == needs:
                    leafs.append(dependency)

        # if not all dependencies were resolved on the way, we
        # have found at least one cyclic dependency
        if len(sorting) < len(artifacts):
            raise CyclicDependencyChainError()

        return sorting

    def _create_build_groups(self, sorting):
        groups = collections.deque()

        if sorting:
            # create the last group
            group = []
            groups.append(group)

            # traverse the build graph in reverse topological order
            for artifact in sorting:
                # add artifact to a group that comes as late in the build order
                # as possible; if the first group contains any dependents,
                # add the artifact to a new group at the beginning of the order
                for group in groups:
                    if not any([x in group for x in artifact.dependents]):
                        group.append(artifact)
                        break
                    else:
                        group = []
                        group.append(artifact)
                        groups.appendleft(group)
                        break

        return groups
