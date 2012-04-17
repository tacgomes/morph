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


class MutualDependencyError(cliapp.AppException):

    def __init__(self, a, b):
        cliapp.AppException.__init__(
                self, 'Cyclic dependency between %s and %s detected' % (a, b))


class CyclicDependencyChainError(cliapp.AppException):

    def __init__(self):
        cliapp.AppException.__init__(
                self, 'Cyclic dependency detected somewhere')


class DependencyOrderError(cliapp.AppException):

    def __init__(self, stratum, chunk, dependency_name):
        cliapp.AppException.__init__(
                self, 'In stratum %s, chunk %s references its dependency %s '
                'before it is defined' % (stratum, chunk, dependency_name))


class DependencyFormatError(cliapp.AppException):

    def __init__(self, stratum, chunk):
        cliapp.AppException.__init__(
                self, 'In stratum %s, chunk %s uses an invalid '
                'build-depends format' % (stratum, chunk))


class BuildGraph(object):

    def compute_build_order(self, source_pool):
        self._realise_dependencies(source_pool)
        sorting = self._compute_topological_sorting(source_pool)
        groups = self._create_build_groups(sorting)
        return groups

    def _realise_dependencies(self, source_pool):
        queue = collections.deque(source_pool)
        while queue:
            source = queue.popleft()

            if source.morphology['kind'] == 'system':
                self._realise_system_dependencies(source, queue, source_pool)
            elif source.morphology['kind'] == 'stratum':
                self._realise_stratum_dependencies(source, queue, source_pool)

    def _realise_system_dependencies(self, system, queue, source_pool):
        for stratum_name in system.morphology['strata']:
            stratum = source_pool.lookup(
                    system.repo.original_name,
                    system.original_ref,
                    '%s.morph' % stratum_name)
            
            system.add_dependency(stratum)
            queue.append(stratum)

    def _realise_stratum_dependencies(self, stratum, queue, source_pool):
        strata = []

        if stratum.morphology['build-depends']:
            for stratum_name in stratum.morphology['build-depends']:
                other_stratum = source_pool.lookup(
                        stratum.repo.original_name,
                        stratum.original_ref,
                        '%s.morph' % stratum_name)
                strata.append(other_stratum)

                if other_stratum.depends_on(stratum):
                    raise MutualDependencyError(stratum, other_stratum)

                stratum.add_dependency(other_stratum)
                queue.append(other_stratum)

        chunks = []
        processed_chunks = []
        name_to_processed_chunk = {}

        for info in stratum.morphology['sources']:
            chunk = source_pool.lookup(
                    info['repo'],
                    info['ref'],
                    '%s.morph' % info['morph'])
            chunks.append(chunk)

            stratum.add_dependency(chunk)

            for other_stratum in strata:
                chunk.add_dependency(other_stratum)

            build_depends = info.get('build-depends', None)

            if build_depends is None:
                for earlier_chunk in processed_chunks:
                    if earlier_chunk.depends_on(chunk):
                        raise MutualDependencyError(chunk, earlier_chunk)
                    chunk.add_dependency(earlier_chunk)
            elif isinstance(build_depends, list):
                for name in build_depends:
                    other_chunk = name_to_processed_chunk.get(name, None)
                    if other_chunk:
                        chunk.add_dependency(other_chunk)
                    else:
                        raise DependencyOrderError(stratum, info['name'], name)
            else:
                raise DependencyFormatError(stratum, info['name'])
            processed_chunks.append(chunk)
            name_to_processed_chunk[info['name']] = chunk

    def _compute_topological_sorting(self, source_pool):
        '''Computes a topological sorting of the build graph. 
        
        A topological sorting basically is the result of a series of
        breadth-first searches starting at each leaf node (sources with no
        dependencies). Sources are added to the sorting as soon as all their
        dependencies have been added (which means that by then, all
        dependencies are satisfied).

        For more information, see
        http://en.wikipedia.org/wiki/Topological_sorting.
        
        '''

        # map sources to sets of satisfied dependencies. this is to detect when
        # we can actually add sources to the BFS queue. rather than dropping
        # links between nodes, like most topological sorting algorithms do,
        # we simply remember all satisfied dependencies and check if all
        # of them are met repeatedly
        satisfied_dependencies = {}

        # create an empty sorting
        sorting = collections.deque()

        # create a set of leafs to start the DFS from
        leafs = collections.deque()
        for source in source_pool:
            satisfied_dependencies[source] = set()
            if len(source.dependencies) == 0:
                leafs.append(source)

        while len(leafs) > 0:
            # fetch a leaf source from the DFS queue
            source = leafs.popleft()

            # add it to the sorting
            sorting.append(source)

            # mark this dependency as resolved
            for dependent in source.dependents:
                satisfied_dependencies[dependent].add(source)

                # add the dependent blob as a leaf if all
                # its dependencies have been resolved
                has = len(satisfied_dependencies[dependent])
                needs = len(dependent.dependencies)
                if has == needs:
                    leafs.append(dependent)

        # if not all dependencies were resolved on the way, we
        # have found at least one cyclic dependency
        if len(sorting) < len(source_pool):
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
