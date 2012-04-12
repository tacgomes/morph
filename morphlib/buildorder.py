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
            sorting = self._compute_topological_sorting(artifacts)
            self.groups = self._create_build_groups(sorting)
        else:
            self.groups = []

    def _compute_topological_sorting(self, artifacts):
        '''Computes a topological sorting of the build graph. 
        
        A topological sorting basically is the result of a series of
        breadth-first searches starting at each leaf node (artifacts with no
        dependencies). Artifacts are added to the sorting as soon as all their
        dependencies have been added (which means that by then, all
        dependencies are satisfied).

        For more information, see
        http://en.wikipedia.org/wiki/Topological_sorting.
        
        '''

        # map artifacts to sets of satisfied dependencies. this is to detect
        # when we can actually add artifacts to the BFS queue. rather than
        # dropping links between nodes, like most topological sorting
        # algorithms do, we simply remember all satisfied dependencies and
        # check if all of them are met repeatedly
        satisfied_dependencies = {}

        # create an empty sorting
        sorting = collections.deque()

        # create a set of leafs to start the DFS from
        leafs = collections.deque()
        for artifact in artifacts:
            satisfied_dependencies[artifact] = set()
            if len(artifact.dependencies) == 0:
                leafs.append(artifact)

        while len(leafs) > 0:
            # fetch a leaf artifact from the DFS queue
            artifact = leafs.popleft()

            # add it to the sorting
            sorting.append(artifact)

            # mark this dependency as resolved in dependent artifacts
            for dependent in artifact.dependents:
                satisfied_dependencies[dependent].add(artifact)

                # add the dependent blob as a leaf if all
                # its dependencies have been resolved
                has = len(satisfied_dependencies[dependent])
                needs = len(dependent.dependencies)
                if has == needs:
                    leafs.append(dependent)

        # if not all dependencies were resolved on the way, we
        # have found at least one cyclic dependency
        if len(sorting) < len(artifacts):
            raise CyclicDependencyChainError()

        return sorting

    def _create_build_groups(self, sorting):
        groups = collections.deque()

        if sorting:
            # create the first group
            group = []
            groups.append(group)

            # traverse the build graph in topological order
            for source in sorting:
                # add the current item to the current group, or a new group
                # if one of its dependencies is in the current one
                create_group = False
                for dependency in source.dependencies:
                    if dependency in group:
                        create_group = True
                if create_group:
                    group = []
                    groups.append(group)
                group.append(source)

        return groups
