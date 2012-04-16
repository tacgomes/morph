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

import morphlib


class MutualDependencyError(cliapp.AppException):

    def __init__(self, a, b):
        cliapp.AppException.__init__(
                self, 'Cyclic dependency between %s and %s detected' % (a, b))


class DependencyOrderError(cliapp.AppException):

    def __init__(self, stratum, chunk, dependency_name):
        cliapp.AppException.__init__(
                self, 'In stratum %s, chunk %s references its dependency %s '
                'before it is defined' %
                (stratum.source, chunk, dependency_name))


class DependencyFormatError(cliapp.AppException):

    def __init__(self, stratum, chunk):
        cliapp.AppException.__init__(
                self, 'In stratum %s, chunk %s uses an invalid '
                'build-depends format' % (stratum.source, chunk))


class UndefinedChunkArtifactError(cliapp.AppException):

    '''Exception raised when non-existent artifacts are referenced.
    
    Usually, this will only occur when a stratum refers to a chunk
    artifact that is not defined in a chunk.
    
    '''

    def __init__(self, parent, reference):
        cliapp.AppException.__init__(
                self, 'Undefined chunk artifact "%s" referenced in ' 
                'stratum %s' % (reference, parent))


class ArtifactResolver(object):

    '''Resolves sources into artifacts that would be build from the sources.
    
    This class takes a CacheKeyComputer and a SourcePool, analyses the
    sources and their dependencies and creates a list of artifacts
    (represented by Artifact objects) that are involved in building the
    sources in the pool.
    
    '''

    def __init__(self, cache_key_computer):
        self.cache_key_computer = cache_key_computer
        self._cached_artifacts = None
        self._added_artifacts = None
        self._source_pool = None

    def resolve_artifacts(self, source_pool):
        self._source_pool = source_pool
        self._cached_artifacts = {}
        self._added_artifacts = set()

        artifacts = self._resolve_artifacts_recursively()
        # TODO perform cycle detection, e.g. based on:
        # http://stackoverflow.com/questions/546655/finding-all-cycles-in-graph
        return artifacts

    def _resolve_artifacts_recursively(self):
        artifacts = []

        queue = self._create_initial_queue()
        while queue:
            source = queue.popleft()

            cache_key = self.cache_key_computer.compute_key(source)

            if source.morphology['kind'] == 'system':
                artifact = self._get_artifact(
                        source, source.morphology['name'], cache_key)

                if not artifact in self._added_artifacts:
                    artifacts.append(artifact)
                    self._added_artifacts.add(artifact)

                resolved_artifacts = self._resolve_system_dependencies(
                        artifact, queue)

                for artifact in resolved_artifacts:
                    if not artifact in self._added_artifacts:
                        artifacts.append(artifact)
                        self._added_artifacts.add(artifact)
            elif source.morphology['kind'] == 'stratum':
                artifact = self._get_artifact(
                        source, source.morphology['name'], cache_key)

                if not artifact in self._added_artifacts:
                    artifacts.append(artifact)
                    self._added_artifacts.add(artifact)

                resolved_artifacts = self._resolve_stratum_dependencies(
                        artifact, queue)

                for artifact in resolved_artifacts:
                    if not artifact in self._added_artifacts:
                        artifacts.append(artifact)
                        self._added_artifacts.add(artifact)
            elif source.morphology['kind'] == 'chunk':
                names = self._chunk_artifact_names(source)
                for name in names:
                    artifact = self._get_artifact(source, name, cache_key)
                    if not artifact in self._added_artifacts:
                        artifacts.append(artifact)
                        self._added_artifacts.add(artifact)

        return artifacts

    def _create_initial_queue(self):
        if all([x.morphology['kind'] == 'chunk' for x in self._source_pool]):
            return collections.deque(self._source_pool)
        else:
            sources = [x for x in self._source_pool
                       if x.morphology['kind'] != 'chunk']
            return collections.deque(sources)

    def _get_artifact(self, source, name, cache_key):
        info = (source, name, cache_key)
        if info in self._cached_artifacts:
            return self._cached_artifacts[info]
        else:
            artifact = morphlib.artifact.Artifact(info[0], info[1], info[2])
            self._cached_artifacts[info] = artifact
            return artifact

    def _resolve_system_dependencies(self, system, queue):
        artifacts = []

        for stratum_name in system.source.morphology['strata']:
            source = self._source_pool.lookup(
                    system.source.repo,
                    system.source.original_ref,
                    '%s.morph' % stratum_name)

            cache_key = self.cache_key_computer.compute_key(source)
            stratum = self._get_artifact(source, stratum_name, cache_key)

            system.add_dependency(stratum)
            queue.append(source)

            artifacts.append(stratum)
        
        return artifacts

    def _resolve_stratum_dependencies(self, stratum, queue):
        artifacts = []

        strata = []

        if stratum.source.morphology['build-depends']:
            for stratum_name in stratum.source.morphology['build-depends']:
                other_source = self._source_pool.lookup(
                        stratum.source.repo,
                        stratum.source.original_ref,
                        '%s.morph' % stratum_name)

                cache_key = self.cache_key_computer.compute_key(other_source)
                other_stratum = self._get_artifact(
                        other_source, stratum_name, cache_key)

                strata.append(other_stratum)

                artifacts.append(other_stratum)

                if other_stratum.depends_on(stratum):
                    raise MutualDependencyError(stratum, other_stratum)

                stratum.add_dependency(other_stratum)
                queue.append(other_source)

        chunk_artifacts = []
        processed_artifacts = []
        name_to_processed_artifact = {}

        for info in stratum.source.morphology['sources']:
            chunk_source = self._source_pool.lookup(
                    info['repo'],
                    info['ref'],
                    '%s.morph' % info['morph'])

            possible_names = self._chunk_artifact_names(chunk_source)
            if not info['name'] in possible_names:
                raise UndefinedChunkArtifactError(stratum.source, info['name'])

            cache_key = self.cache_key_computer.compute_key(chunk_source)
            
            chunk_artifact = self._get_artifact(
                    chunk_source, info['name'], cache_key)
            chunk_artifacts.append(chunk_artifact)

            artifacts.append(chunk_artifact)

            stratum.add_dependency(chunk_artifact)

            for other_stratum in strata:
                chunk_artifact.add_dependency(other_stratum)

            build_depends = info.get('build-depends', None)

            if build_depends is None:
                for earlier_artifact in processed_artifacts:
                    if earlier_artifact is chunk_artifact:
                        continue
                    if earlier_artifact.depends_on(chunk_artifact):
                        raise MutualDependencyError(
                                chunk_artifact, earlier_artifact)
                    chunk_artifact.add_dependency(earlier_artifact)
            elif isinstance(build_depends, list):
                for name in build_depends:
                    other_artifact = name_to_processed_artifact.get(name, None)
                    if other_artifact is chunk_artifact:
                        continue
                    if other_artifact:
                        chunk_artifact.add_dependency(other_artifact)
                    else:
                        raise DependencyOrderError(
                                stratum, info['name'], name)
            else:
                raise DependencyFormatError(stratum, info['name'])
            processed_artifacts.append(chunk_artifact)
            name_to_processed_artifact[info['name']] = chunk_artifact

        return artifacts

    def _chunk_artifact_names(self, source):
        if 'chunks' in source.morphology:
            return sorted(source.morphology['chunks'].keys())
        else:
            return [source.morphology['name']]
