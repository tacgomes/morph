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


class DependencyResolverTests(unittest.TestCase):

    def setUp(self):
        self.resolver = morphlib.dependencyresolver.DependencyResolver()

    def test_create_empty_build_order_for_empty_pool(self):
        pool = morphlib.sourcepool.SourcePool()
        self.resolver.resolve_dependencies(pool)

    def test_with_a_single_chunk(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "foo",
                    "kind": "chunk",
                    "artifacts": {
                        "foo-runtime": [ "usr/bin" ],
                        "foo-devel":   [ "usr/lib" ]
                    }
                }
                ''')
        chunk = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'foo.morph')
        pool.add(chunk)

        self.resolver.resolve_dependencies(pool)
        
        self.assertEqual(chunk.dependencies, [])
        self.assertEqual(chunk.dependents, [])

    def test_with_a_single_empty_stratum(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "foo",
                    "kind": "stratum"
                }
                ''')
        stratum = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'foo.morph')
        pool.add(stratum)

        self.resolver.resolve_dependencies(pool)

        self.assertEqual(stratum.dependencies, [])
        self.assertEqual(stratum.dependents, [])

    def test_with_a_single_empty_system(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "foo",
                    "kind": "system"
                }
                ''')
        system = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'foo.morph')
        pool.add(system)

        self.resolver.resolve_dependencies(pool)

        self.assertEqual(system.dependencies, [])
        self.assertEqual(system.dependents, [])

    def test_with_a_one_chunk_stratum(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        stratum = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk",
                    "kind": "chunk",
                    "artifacts": {
                        "foo-runtime": [ "usr/bin" ],
                        "foo-devel":   [ "usr/lib" ]
                    }
                }
                ''')
        chunk = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk.morph')
        pool.add(chunk)

        self.resolver.resolve_dependencies(pool)

        self.assertEqual(chunk.dependencies, [])
        self.assertEqual(chunk.dependents, [stratum])
        self.assertEqual(stratum.dependencies, [chunk])
        self.assertEqual(stratum.dependents, [])

    def test_with_a_one_chunk_artifact_stratum(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "chunk-runtime",
                            "morph": "chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        stratum = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk",
                    "kind": "chunk",
                    "artifacts": {
                        "foo-runtime": [ "usr/bin" ],
                        "foo-devel":   [ "usr/lib" ]
                    }
                }
                ''')
        chunk = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk.morph')
        pool.add(chunk)

        self.resolver.resolve_dependencies(pool)

        self.assertEqual(chunk.dependencies, [])
        self.assertEqual(chunk.dependents, [stratum])
        self.assertEqual(stratum.dependencies, [chunk])
        self.assertEqual(stratum.dependents, [])

    def test_with_stratum_and_implicit_dependencies(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "chunk1",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "chunk2",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "chunk3",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        stratum = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk1",
                    "kind": "chunk"
                }
                ''')
        chunk1 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk1.morph')
        pool.add(chunk1)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk2",
                    "kind": "chunk"
                }
                ''')
        chunk2 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk2.morph')
        pool.add(chunk2)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk3",
                    "kind": "chunk"
                }
                ''')
        chunk3 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk3.morph')
        pool.add(chunk3)

        self.resolver.resolve_dependencies(pool)

        self.assertEqual(chunk1.dependencies, [])
        self.assertEqual(chunk1.dependents, [stratum, chunk2, chunk3])
        self.assertEqual(chunk2.dependencies, [chunk1])
        self.assertEqual(chunk2.dependents, [stratum, chunk3])
        self.assertEqual(chunk3.dependencies, [chunk1, chunk2])
        self.assertEqual(chunk3.dependents, [stratum])
        self.assertEqual(stratum.dependencies, [chunk1, chunk2, chunk3])
        self.assertEqual(stratum.dependents, [])

    def test_with_explicit_dependencies(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "chunk1",
                            "repo": "repo",
                            "ref": "original/ref",
                            "build-depends": []
                        },
                        {
                            "name": "chunk2",
                            "repo": "repo",
                            "ref": "original/ref",
                            "build-depends": []
                        },
                        {
                            "name": "chunk3",
                            "repo": "repo",
                            "ref": "original/ref",
                            "build-depends": [
                                "chunk1",
                                "chunk2"
                            ]
                        }
                    ]
                }
                ''')
        stratum = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk1",
                    "kind": "chunk"
                }
                ''')
        chunk1 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk1.morph')
        pool.add(chunk1)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk2",
                    "kind": "chunk"
                }
                ''')
        chunk2 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk2.morph')
        pool.add(chunk2)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk3",
                    "kind": "chunk"
                }
                ''')
        chunk3 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk3.morph')
        pool.add(chunk3)

        self.resolver.resolve_dependencies(pool)

        self.assertEqual(chunk1.dependencies, [])
        self.assertEqual(chunk1.dependents, [stratum, chunk3])
        self.assertEqual(chunk2.dependencies, [])
        self.assertEqual(chunk2.dependents, [stratum, chunk3])
        self.assertEqual(chunk3.dependencies, [chunk1, chunk2])
        self.assertEqual(chunk3.dependents, [stratum])
        self.assertEqual(stratum.dependencies, [chunk1, chunk2, chunk3])
        self.assertEqual(stratum.dependents, [])

    def test_with_stratum_dependencies(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum1",
                    "kind": "stratum"
                }
                ''')
        stratum1 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum1.morph')
        pool.add(stratum1)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum2",
                    "kind": "stratum",
                    "build-depends": [
                        "stratum1"
                    ]
                }
                ''')
        stratum2 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum2.morph')
        pool.add(stratum2)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum3",
                    "kind": "stratum",
                    "build-depends": [
                        "stratum2"
                    ]
                }
                ''')
        stratum3 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum3.morph')
        pool.add(stratum3)

        self.resolver.resolve_dependencies(pool)

        self.assertEqual(stratum1.dependencies, [])
        self.assertEqual(stratum1.dependents, [stratum2])
        self.assertEqual(stratum2.dependencies, [stratum1])
        self.assertEqual(stratum2.dependents, [stratum3])
        self.assertEqual(stratum3.dependencies, [stratum2])
        self.assertEqual(stratum3.dependents, [])

    def test_with_stratum_and_chunk_dependencies(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum1",
                    "kind": "stratum"
                }
                ''')
        stratum1 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum1.morph')
        pool.add(stratum1)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum2",
                    "kind": "stratum",
                    "build-depends": [
                        "stratum1"
                    ],
                    "sources": [
                        {
                            "name": "chunk1",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "chunk2",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        stratum2 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum2.morph')
        pool.add(stratum2)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk1",
                    "kind": "chunk"
                }
                ''')
        chunk1 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk1.morph')
        pool.add(chunk1)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk2",
                    "kind": "chunk"
                }
                ''')
        chunk2 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk2.morph')
        pool.add(chunk2)

        self.resolver.resolve_dependencies(pool)

        self.assertEqual(stratum1.dependencies, [])
        self.assertEqual(stratum1.dependents, [stratum2, chunk1, chunk2])
        self.assertEqual(chunk1.dependencies, [stratum1])
        self.assertEqual(chunk1.dependents, [stratum2, chunk2])
        self.assertEqual(chunk2.dependencies, [stratum1, chunk1])
        self.assertEqual(chunk2.dependents, [stratum2])
        self.assertEqual(stratum2.dependencies, [stratum1, chunk1, chunk2])
        self.assertEqual(stratum2.dependents, [])

    def test_with_a_system_and_two_strata(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum1",
                    "kind": "stratum"
                }
                ''')
        stratum1 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum1.morph')
        pool.add(stratum1)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum2",
                    "kind": "stratum"
                }
                ''')
        stratum2 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum2.morph')
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
                'repo', 'original/ref', 'sha1', morph, 'system.morph')
        pool.add(system)

        self.resolver.resolve_dependencies(pool)

        self.assertEqual(stratum1.dependencies, [])
        self.assertEqual(stratum1.dependents, [system])
        self.assertEqual(stratum2.dependencies, [])
        self.assertEqual(stratum2.dependents, [system])
        self.assertEqual(system.dependencies, [stratum1, stratum2])
        self.assertEqual(system.dependents, [])

    def test_detection_of_mutual_dependency_between_two_strata(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum1",
                    "kind": "stratum",
                    "build-depends": [
                        "stratum2"
                    ]
                }
                ''')
        stratum1 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum1.morph')
        pool.add(stratum1)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum2",
                    "kind": "stratum",
                    "build-depends": [
                        "stratum1"
                    ]
                }
                ''')
        stratum2 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum2.morph')
        pool.add(stratum2)

        self.assertRaises(morphlib.dependencyresolver.MutualDependencyError,
                          self.resolver.resolve_dependencies, pool)

    def test_detection_of_mutual_dependency_between_consecutive_chunks(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum1",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "chunk1",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "chunk2",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        stratum1 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum1.morph')
        pool.add(stratum1)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum2",
                    "kind": "stratum",
                    "build-depends": [
                        "stratum1"
                    ],
                    "sources": [
                        {
                            "name": "chunk2",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "chunk1",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        stratum2 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum2.morph')
        pool.add(stratum2)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk1",
                    "kind": "chunk"
                }
                ''')
        chunk1 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk1.morph')
        pool.add(chunk1)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk2",
                    "kind": "chunk"
                }
                ''')
        chunk2 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk2.morph')
        pool.add(chunk2)

        self.assertRaises(morphlib.dependencyresolver.MutualDependencyError,
                          self.resolver.resolve_dependencies, pool)

    def test_detection_of_cyclic_chunk_dependency_chain(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum1",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "chunk1",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "chunk2",
                            "repo": "repo",
                            "ref": "original/ref",
                            "build-depends": [
                                "chunk1"
                            ]
                        },
                        {
                            "name": "chunk3",
                            "repo": "repo",
                            "ref": "original/ref",
                            "build-depends": [
                                "chunk2"
                            ]
                        }
                    ]
                }
                ''')
        stratum1 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum1.morph')
        pool.add(stratum1)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum2",
                    "kind": "stratum",
                    "build-depends": [
                        "stratum1"
                    ],
                    "sources": [
                        {
                            "name": "chunk3",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "chunk1",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        stratum2 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum2.morph')
        pool.add(stratum2)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk1",
                    "kind": "chunk"
                }
                ''')
        chunk1 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk1.morph')
        pool.add(chunk1)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk2",
                    "kind": "chunk"
                }
                ''')
        chunk2 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk2.morph')
        pool.add(chunk2)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk3",
                    "kind": "chunk"
                }
                ''')
        chunk2 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk3.morph')
        pool.add(chunk2)

        self.assertRaises(
                morphlib.dependencyresolver.CyclicDependencyChainError,
                self.resolver.resolve_dependencies, pool)

    def test_detection_of_chunk_dependencies_in_invalid_order(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "chunk1",
                            "repo": "repo",
                            "ref": "original/ref",
                            "build-depends": [
                                "chunk2"
                            ]
                        },
                        {
                            "name": "chunk2",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        stratum = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk1",
                    "kind": "chunk"
                }
                ''')
        chunk1 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk1.morph')
        pool.add(chunk1)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk2",
                    "kind": "chunk"
                }
                ''')
        chunk2 = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk2.morph')
        pool.add(chunk2)

        self.assertRaises(morphlib.dependencyresolver.DependencyOrderError,
                          self.resolver.resolve_dependencies, pool)

    def test_detection_of_invalid_build_depends_format(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "chunk",
                            "repo": "repo",
                            "ref": "original/ref",
                            "build-depends": "whatever"
                        }
                    ]
                }
                ''')
        stratum = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk",
                    "kind": "chunk"
                }
                ''')
        chunk = morphlib.source.Source(
                'repo', 'original/ref', 'sha1', morph, 'chunk.morph')
        pool.add(chunk)

        self.assertRaises(morphlib.dependencyresolver.DependencyFormatError,
                          self.resolver.resolve_dependencies, pool)
