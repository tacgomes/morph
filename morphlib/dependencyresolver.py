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
                self, 'Cyclic dependency chain detected')


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


class DependencyResolver(object):

    def resolve_dependencies(self, source_pool):
        queue = collections.deque(source_pool)
        while queue:
            source = queue.popleft()

            if source.morphology['kind'] == 'system':
                self._resolve_system_dependencies(source, queue, source_pool)
            elif source.morphology['kind'] == 'stratum':
                self._resolve_stratum_dependencies(source, queue, source_pool)

        self._detect_cyclic_dependencies(source_pool)

    def _resolve_system_dependencies(self, system, queue, source_pool):
        for stratum_name in system.morphology['strata']:
            stratum = source_pool.lookup(
                    system.repo,
                    system.original_ref,
                    '%s.morph' % stratum_name)
            
            system.add_dependency(stratum)
            queue.append(stratum)

    def _resolve_stratum_dependencies(self, stratum, queue, source_pool):
        strata = []

        if stratum.morphology['build-depends']:
            for stratum_name in stratum.morphology['build-depends']:
                other_stratum = source_pool.lookup(
                        stratum.repo,
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
                    if earlier_chunk is chunk:
                        continue
                    if earlier_chunk.depends_on(chunk):
                        raise MutualDependencyError(chunk, earlier_chunk)
                    chunk.add_dependency(earlier_chunk)
            elif isinstance(build_depends, list):
                for name in build_depends:
                    other_chunk = name_to_processed_chunk.get(name, None)
                    if other_chunk is chunk:
                        continue
                    if other_chunk:
                        chunk.add_dependency(other_chunk)
                    else:
                        raise DependencyOrderError(stratum, info['name'], name)
            else:
                raise DependencyFormatError(stratum, info['name'])
            processed_chunks.append(chunk)
            name_to_processed_chunk[info['name']] = chunk

    def _detect_cyclic_dependencies(self, source_pool):
        # FIXME This is not well tested and might be incorrect. Better
        # something based on
        # http://stackoverflow.com/questions/546655/finding-all-cycles-in-graph

        visited = set()
        explored = set()
        parent = {}

        roots = []
        for source in source_pool:
            if len(source.dependents) == 0:
                roots.append(source)
                parent[source] = None

        stack = collections.deque(roots)
        while stack:
            source = stack.popleft()
            visited.add(source)

            for dependency in source.dependencies:
                if not (source, dependency) in explored:
                    explored.add((source, dependency))
                    parent[dependency] = source
                    if not dependency in visited:
                        stack.appendleft(dependency)
                    else:
                        raise CyclicDependencyChainError()
