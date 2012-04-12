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


import json
import unittest

import morphlib


class FakeCacheKeyComputer(object):
    '''Fake computer that uses the uppercase source name as the cache key.'''

    def compute_key(self, source):
        return source.morphology['name'].upper()


class FakeChunkMorphology(morphlib.morph2.Morphology):

    def __init__(self, name, artifact_names=[]):
        assert(isinstance(artifact_names, list))

        if artifact_names:
            # fake a list of artifacts
            artifacts = {}
            for artifact_name in artifact_names:
                artifacts[artifact_name] = [artifact_name]
            text = ('''
                    {
                        "name": "%s",
                        "kind": "chunk",
                        "artifacts": %s
                    }
                    ''' % (name, json.dumps(artifacts)))
        else:
            text = ('''
                    {
                        "name": "%s",
                        "kind": "chunk"
                    }
                    ''' % name)
        morphlib.morph2.Morphology.__init__(self, text)


class FakeStratumMorphology(morphlib.morph2.Morphology):

    def __init__(self, name, source_list=[], build_depends=[]):
        assert(isinstance(source_list, list))
        assert(isinstance(build_depends, list))

        if source_list:
            sources = []
            for source_name, morph, repo, ref in source_list:
                sources.append({
                    'name': source_name,
                    'morph': morph,
                    'repo': repo,
                    'ref': ref
                })
            text = ('''
                    {
                        "name": "%s",
                        "kind": "stratum",
                        "build-depends": %s,
                        "sources": %s
                    }
                    ''' % (name,
                           json.dumps(build_depends),
                           json.dumps(sources)))
        else:
            text = ('''
                    {
                        "name": "%s",
                        "kind": "stratum",
                        "build-depends": %s
                    }
                    ''' % (name,
                           json.dumps(build_depends)))
        morphlib.morph2.Morphology.__init__(self, text)


class ArtifactResolverTests(unittest.TestCase):

    def setUp(self):
        self.cache_key_computer = FakeCacheKeyComputer()
        self.dependency_resolver = \
            morphlib.dependencyresolver.DependencyResolver()
        self.resolver = morphlib.artifactresolver.ArtifactResolver(
                self.cache_key_computer)

    def test_resolve_artifacts_using_an_empty_pool(self):
        pool = morphlib.sourcepool.SourcePool()
        artifacts = self.resolver.resolve_artifacts(pool)
        self.assertEqual(len(artifacts), 0)

    def test_resolve_single_chunk_with_no_subartifacts(self):
        pool = morphlib.sourcepool.SourcePool()
        
        morph = FakeChunkMorphology('chunk')
        source = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'chunk.morph')
        pool.add(source)

        artifacts = self.resolver.resolve_artifacts(pool)

        self.assertEqual(len(artifacts), 1)

        self.assertEqual(artifacts[0].source, source)
        self.assertEqual(artifacts[0].name, 'chunk')
        self.assertEqual(artifacts[0].cache_key, 'CHUNK')

    def test_resolve_single_chunk_with_one_artifact(self):
        pool = morphlib.sourcepool.SourcePool()
        
        morph = FakeChunkMorphology('chunk', ['chunk-runtime'])
        source = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'chunk.morph')
        pool.add(source)

        artifacts = self.resolver.resolve_artifacts(pool)

        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0].source, source)
        self.assertEqual(artifacts[0].name, 'chunk-runtime')
        self.assertEqual(artifacts[0].cache_key, 'CHUNK')

    def test_resolve_single_chunk_with_two_artifact(self):
        pool = morphlib.sourcepool.SourcePool()
        
        morph = FakeChunkMorphology('chunk', ['chunk-runtime', 'chunk-devel'])
        source = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'chunk.morph')
        pool.add(source)

        artifacts = self.resolver.resolve_artifacts(pool)

        self.assertEqual(len(artifacts), 2)

        self.assertEqual(artifacts[0].source, source)
        self.assertEqual(artifacts[0].name, 'chunk-devel')
        self.assertEqual(artifacts[0].cache_key, 'CHUNK')

        self.assertEqual(artifacts[1].source, source)
        self.assertEqual(artifacts[1].name, 'chunk-runtime')
        self.assertEqual(artifacts[1].cache_key, 'CHUNK')

    def test_resolve_stratum_and_chunk_with_no_subartifacts(self):
        pool = morphlib.sourcepool.SourcePool()
        
        morph = FakeChunkMorphology('chunk')
        chunk = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'chunk.morph')
        pool.add(chunk)

        morph = FakeStratumMorphology(
                'stratum', [('chunk', 'chunk', 'repo', 'ref')])
        stratum = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        self.dependency_resolver.resolve_dependencies(pool)

        artifacts = self.resolver.resolve_artifacts(pool)

        self.assertEqual(len(artifacts), 2)

        self.assertEqual(artifacts[0].source, stratum)
        self.assertEqual(artifacts[0].name, 'stratum')
        self.assertEqual(artifacts[0].cache_key, 'STRATUM')

        self.assertEqual(artifacts[1].source, chunk)
        self.assertEqual(artifacts[1].name, 'chunk')
        self.assertEqual(artifacts[1].cache_key, 'CHUNK')

    def test_resolve_stratum_and_chunk_with_two_subartifacts(self):
        pool = morphlib.sourcepool.SourcePool()
        
        morph = FakeChunkMorphology('chunk', ['chunk-devel', 'chunk-runtime'])
        chunk = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'chunk.morph')
        pool.add(chunk)

        morph = FakeStratumMorphology(
                'stratum', [
                    ('chunk-devel', 'chunk', 'repo', 'ref'),
                    ('chunk-runtime', 'chunk', 'repo', 'ref')
                ])
        stratum = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        self.dependency_resolver.resolve_dependencies(pool)

        artifacts = self.resolver.resolve_artifacts(pool)

        self.assertEqual(len(artifacts), 3)

        self.assertEqual(artifacts[0].source, stratum)
        self.assertEqual(artifacts[0].name, 'stratum')
        self.assertEqual(artifacts[0].cache_key, 'STRATUM')

        self.assertEqual(artifacts[1].source, chunk)
        self.assertEqual(artifacts[1].name, 'chunk-devel')
        self.assertEqual(artifacts[1].cache_key, 'CHUNK')

        self.assertEqual(artifacts[2].source, chunk)
        self.assertEqual(artifacts[2].name, 'chunk-runtime')
        self.assertEqual(artifacts[2].cache_key, 'CHUNK')

    def test_resolve_stratum_and_chunk_with_one_used_subartifacts(self):
        pool = morphlib.sourcepool.SourcePool()
        
        morph = FakeChunkMorphology('chunk', ['chunk-devel', 'chunk-runtime'])
        chunk = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'chunk.morph')
        pool.add(chunk)

        morph = FakeStratumMorphology(
                'stratum', [
                    ('chunk-runtime', 'chunk', 'repo', 'ref')
                ])
        stratum = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        self.dependency_resolver.resolve_dependencies(pool)

        artifacts = self.resolver.resolve_artifacts(pool)

        self.assertEqual(len(artifacts), 2)

        self.assertEqual(artifacts[0].source, stratum)
        self.assertEqual(artifacts[0].name, 'stratum')
        self.assertEqual(artifacts[0].cache_key, 'STRATUM')

        self.assertEqual(artifacts[1].source, chunk)
        self.assertEqual(artifacts[1].name, 'chunk-runtime')
        self.assertEqual(artifacts[1].cache_key, 'CHUNK')

    def test_resolving_two_different_chunk_artifacts_in_a_stratum(self):
        pool = morphlib.sourcepool.SourcePool()
        
        morph = FakeChunkMorphology('foo')
        foo_chunk = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'foo.morph')
        pool.add(foo_chunk)

        morph = FakeChunkMorphology('bar')
        bar_chunk = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'bar.morph')
        pool.add(bar_chunk)

        morph = FakeStratumMorphology(
                'stratum', [
                    ('foo', 'foo', 'repo', 'ref'),
                    ('bar', 'bar', 'repo', 'ref')
                ])
        stratum = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        self.dependency_resolver.resolve_dependencies(pool)

        artifacts = self.resolver.resolve_artifacts(pool)

        self.assertEqual(len(artifacts), 3)

        self.assertEqual(artifacts[0].source, stratum)
        self.assertEqual(artifacts[0].name, 'stratum')
        self.assertEqual(artifacts[0].cache_key, 'STRATUM')

        self.assertEqual(artifacts[1].source, foo_chunk)
        self.assertEqual(artifacts[1].name, 'foo')
        self.assertEqual(artifacts[1].cache_key, 'FOO')

        self.assertEqual(artifacts[2].source, bar_chunk)
        self.assertEqual(artifacts[2].name, 'bar')
        self.assertEqual(artifacts[2].cache_key, 'BAR')

    def test_resolving_artifacts_for_a_chain_of_two_strata(self):
        pool = morphlib.sourcepool.SourcePool()
        
        morph = FakeStratumMorphology('stratum1')
        stratum1 = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'stratum1.morph')
        pool.add(stratum1)

        morph = FakeStratumMorphology('stratum2', [], ['stratum1'])
        stratum2 = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'stratum2.morph')
        pool.add(stratum2)

        self.dependency_resolver.resolve_dependencies(pool)

        artifacts = self.resolver.resolve_artifacts(pool)

        self.assertEqual(len(artifacts), 2)

        self.assertEqual(artifacts[0].source, stratum2)
        self.assertEqual(artifacts[0].name, 'stratum2')
        self.assertEqual(artifacts[0].cache_key, 'STRATUM2')

        self.assertEqual(artifacts[1].source, stratum1)
        self.assertEqual(artifacts[1].name, 'stratum1')
        self.assertEqual(artifacts[1].cache_key, 'STRATUM1')

    def test_resolving_artifacts_for_a_system_with_two_strata(self):
        pool = morphlib.sourcepool.SourcePool()
        
        morph = FakeStratumMorphology('stratum1')
        stratum1 = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'stratum1.morph')
        pool.add(stratum1)

        morph = FakeStratumMorphology('stratum2', [], ['stratum1'])
        stratum2 = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'stratum2.morph')
        pool.add(stratum2)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "system",
                    "kind": "system",
                    "strata": [
                        "stratum1", 
                        "stratum2"
                    ]
                }
                ''')
        system = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'system.morph')
        pool.add(system)

        self.dependency_resolver.resolve_dependencies(pool)

        artifacts = self.resolver.resolve_artifacts(pool)

        self.assertEqual(len(artifacts), 4)

        self.assertEqual(artifacts[0].source, system)
        self.assertEqual(artifacts[0].name, 'system')
        self.assertEqual(artifacts[0].cache_key, 'SYSTEM')

        self.assertEqual(artifacts[1].source, stratum1)
        self.assertEqual(artifacts[1].name, 'stratum1')
        self.assertEqual(artifacts[1].cache_key, 'STRATUM1')

        self.assertEqual(artifacts[2].source, stratum2)
        self.assertEqual(artifacts[2].name, 'stratum2')
        self.assertEqual(artifacts[2].cache_key, 'STRATUM2')

        self.assertEqual(artifacts[3].source, stratum1)
        self.assertEqual(artifacts[3].name, 'stratum1')
        self.assertEqual(artifacts[3].cache_key, 'STRATUM1')

    def test_detection_of_invalid_chunk_artifact_references(self):
        pool = morphlib.sourcepool.SourcePool()
        
        morph = FakeChunkMorphology('chunk')
        chunk = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'chunk.morph')
        pool.add(chunk)

        morph = FakeStratumMorphology(
                'stratum', [
                    ('chunk-runtime', 'chunk', 'repo', 'ref')
                ])
        stratum = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        self.dependency_resolver.resolve_dependencies(pool)

        self.assertRaises(
                morphlib.artifactresolver.UndefinedChunkArtifactError,
                self.resolver.resolve_artifacts, pool)
