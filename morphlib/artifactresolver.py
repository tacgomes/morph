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


class UndefinedChunkArtifactError(cliapp.AppException):

    '''Exception raised when non-existent artifacts are referenced.
    
    Usually, this will only occur when a stratum refers to a chunk
    artifact that is not defined in a chunk.
    
    '''

    def __init__(self, parent, reference):
        cliapp.AppException.__init__(
                self, 'Undefined chunk artifact "%s" referenced in %s' %
                    (reference, parent))


class ArtifactResolver(object):

    '''Resolves sources into artifacts that would be build from the sources.
    
    This class takes a CacheKeyComputer and a SourcePool, analyses the
    sources and their dependencies and creates a list of artifacts
    (represented by Artifact objects) that are involved in building the
    sources in the pool.
    
    '''

    def __init__(self, cache_key_computer):
        self.cache_key_computer = cache_key_computer

    def resolve_artifacts(self, source_pool):
        artifacts = []
        roots = [x for x in source_pool if not x.dependents]
        queue = collections.deque(roots)
        while queue:
            source = queue.popleft()
            cache_key = self.cache_key_computer.compute_key(source)
            if source.morphology['kind'] == 'system':
                artifact = morphlib.artifact.Artifact(
                        source, source.morphology['name'], cache_key)
                artifacts.append(artifact)
                for dependency in source.dependencies:
                    queue.append(dependency)
            elif source.morphology['kind'] == 'stratum':
                artifact = morphlib.artifact.Artifact(
                        source, source.morphology['name'], cache_key)
                artifacts.append(artifact)
                for dependency in source.dependencies:
                    if dependency.morphology['kind'] == 'stratum':
                        queue.append(dependency)
                    elif dependency.morphology['kind'] == 'chunk':
                        chunk_artifacts = self._find_required_chunk_artifacts(
                                source, dependency, source_pool)
                        artifacts.extend(chunk_artifacts)
            elif source.morphology['kind'] == 'chunk':
                names = self._chunk_artifact_names(source)
                for name in names:
                    artifact = morphlib.artifact.Artifact(
                            source, name, cache_key)
                    artifacts.append(artifact)

        return artifacts

    def _find_required_chunk_artifacts(self, stratum, chunk, source_pool):
        artifacts = []
        for source in stratum.morphology['sources']:
            if self._source_matches_chunk(stratum, source, chunk, source_pool):
                cache_key = self.cache_key_computer.compute_key(chunk)
                artifact = morphlib.artifact.Artifact(
                        chunk, source['name'], cache_key)
                artifacts.append(artifact)
        return artifacts

    def _source_matches_chunk(self, stratum, source, chunk, source_pool):
        source_from_pool = source_pool.lookup(
                source['repo'],
                source['ref'],
                '%s.morph' % source['morph'])

        if source_from_pool is not chunk:
            return False

        chunk_names = self._chunk_artifact_names(chunk)
        
        if source['name'] not in chunk_names:
            raise UndefinedChunkArtifactError(stratum, source['name'])

        return True

    def _chunk_artifact_names(self, chunk):
        if 'artifacts' in chunk.morphology:
            return sorted(chunk.morphology['artifacts'].keys())
        else:
            return [chunk.morphology['name']]

