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


import collections
import unittest

import morphlib.buildgraph
import morphlib.source


class BuildGraphTests(unittest.TestCase):

    def setUp(self):
        self.graph = morphlib.buildgraph.BuildGraph()
        self.repo = morphlib.cachedrepo.CachedRepo('repo', 'url', 'path')

    def test_create_empty_build_order_for_empty_pool(self):
        pool = morphlib.sourcepool.SourcePool()
        order = self.graph.compute_build_order(pool)
        self.assertEqual(order, collections.deque())

    def test_build_order_with_a_single_chunk(self):
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
        source = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'foo.morph')
        pool.add(source)
        
        order = self.graph.compute_build_order(pool)
        desired_order = collections.deque([
                [source]
        ])
        self.assertEqual(order, desired_order)

    def test_build_order_with_a_single_empty_stratum(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "foo",
                    "kind": "stratum"
                }
                ''')
        source = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'foo.morph')
        pool.add(source)

        order = self.graph.compute_build_order(pool)
        desired_order = collections.deque([
                [source]
        ])
        self.assertEqual(order, desired_order)

    def test_build_order_with_a_single_empty_system(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "foo",
                    "kind": "system"
                }
                ''')
        source = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'foo.morph')
        pool.add(source)

        order = self.graph.compute_build_order(pool)
        desired_order = collections.deque([
                [source]
        ])
        self.assertEqual(order, desired_order)

    def test_build_order_with_a_one_chunk_stratum(self):
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
                self.repo, 'original/ref', 'sha1', morph, 'stratum.morph')
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
                self.repo, 'original/ref', 'sha1', morph, 'chunk.morph')
        pool.add(chunk)

        order = self.graph.compute_build_order(pool)
        desired_order = collections.deque([
            [chunk],
            [stratum]
        ])
        self.assertEqual(order, desired_order)

        self.assertEqual(stratum.dependencies, [chunk])

    def test_build_order_with_a_one_chunk_artifact_stratum(self):
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
                self.repo, 'original/ref', 'sha1', morph, 'stratum.morph')
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
                self.repo, 'original/ref', 'sha1', morph, 'chunk.morph')
        pool.add(chunk)

        order = self.graph.compute_build_order(pool)
        desired_order = collections.deque([
            [chunk],
            [stratum]
        ])
        self.assertEqual(order, desired_order)

        self.assertEqual(stratum.dependencies, [chunk])

    def test_build_order_with_stratum_and_implicit_dependencies(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "first-chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "second-chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "third-chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "first-chunk",
                    "kind": "chunk"
                }
                ''')
        first_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'first-chunk.morph')
        pool.add(first_chunk)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "second-chunk",
                    "kind": "chunk"
                }
                ''')
        second_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'second-chunk.morph')
        pool.add(second_chunk)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "third-chunk",
                    "kind": "chunk"
                }
                ''')
        third_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'third-chunk.morph')
        pool.add(third_chunk)

        order = self.graph.compute_build_order(pool)
        desired_order = collections.deque([
            [first_chunk],
            [second_chunk],
            [third_chunk],
            [stratum]
        ])
        self.assertEqual(order, desired_order)

        self.assertEqual(first_chunk.dependencies, [])
        self.assertEqual(second_chunk.dependencies, [first_chunk])
        self.assertEqual(third_chunk.dependencies, [first_chunk, second_chunk])
        self.assertEqual(stratum.dependencies,
                         [first_chunk, second_chunk, third_chunk])

    def test_build_order_with_explicit_dependencies(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "first-chunk",
                            "repo": "repo",
                            "ref": "original/ref",
                            "build-depends": []
                        },
                        {
                            "name": "second-chunk",
                            "repo": "repo",
                            "ref": "original/ref",
                            "build-depends": []
                        },
                        {
                            "name": "third-chunk",
                            "repo": "repo",
                            "ref": "original/ref",
                            "build-depends": [
                                "first-chunk",
                                "second-chunk"
                            ]
                        }
                    ]
                }
                ''')
        stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "first-chunk",
                    "kind": "chunk"
                }
                ''')
        first_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'first-chunk.morph')
        pool.add(first_chunk)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "second-chunk",
                    "kind": "chunk"
                }
                ''')
        second_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'second-chunk.morph')
        pool.add(second_chunk)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "third-chunk",
                    "kind": "chunk"
                }
                ''')
        third_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'third-chunk.morph')
        pool.add(third_chunk)

        order = self.graph.compute_build_order(pool)
        desired_order = collections.deque([
            [first_chunk, second_chunk],
            [third_chunk],
            [stratum]
        ])
        self.assertEqual(order, desired_order)

        self.assertEqual(first_chunk.dependencies, [])
        self.assertEqual(second_chunk.dependencies, [])
        self.assertEqual(third_chunk.dependencies, [first_chunk, second_chunk])
        self.assertEqual(stratum.dependencies,
                         [first_chunk, second_chunk, third_chunk])

    def test_build_order_with_stratum_dependencies(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "first-stratum",
                    "kind": "stratum"
                }
                ''')
        first_stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'first-stratum.morph')
        pool.add(first_stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "second-stratum",
                    "kind": "stratum",
                    "build-depends": [
                        "first-stratum"
                    ]
                }
                ''')
        second_stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'second-stratum.morph')
        pool.add(second_stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "third-stratum",
                    "kind": "stratum",
                    "build-depends": [
                        "second-stratum"
                    ]
                }
                ''')
        third_stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'third-stratum.morph')
        pool.add(third_stratum)

        order = self.graph.compute_build_order(pool)
        desired_order = collections.deque([
            [first_stratum],
            [second_stratum],
            [third_stratum]
        ])
        self.assertEqual(order, desired_order)

        self.assertEqual(first_stratum.dependencies, [])
        self.assertEqual(second_stratum.dependencies, [first_stratum])
        self.assertEqual(third_stratum.dependencies, [second_stratum])

    def test_build_order_with_stratum_and_chunk_dependencies(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "first-stratum",
                    "kind": "stratum"
                }
                ''')
        first_stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'first-stratum.morph')
        pool.add(first_stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "second-stratum",
                    "kind": "stratum",
                    "build-depends": [
                        "first-stratum"
                    ],
                    "sources": [
                        {
                            "name": "first-chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "second-chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        second_stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'second-stratum.morph')
        pool.add(second_stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "first-chunk",
                    "kind": "chunk"
                }
                ''')
        first_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'first-chunk.morph')
        pool.add(first_chunk)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "second-chunk",
                    "kind": "chunk"
                }
                ''')
        second_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'second-chunk.morph')
        pool.add(second_chunk)

        order = self.graph.compute_build_order(pool)
        desired_order = collections.deque([
            [first_stratum],
            [first_chunk],
            [second_chunk],
            [second_stratum]
        ])
        self.assertEqual(order, desired_order)

        self.assertEqual(first_stratum.dependencies, [])
        self.assertEqual(first_chunk.dependencies, [first_stratum])
        self.assertEqual(second_chunk.dependencies,
                         [first_stratum, first_chunk])
        self.assertEqual(second_stratum.dependencies,
                         [first_stratum, first_chunk, second_chunk])

    def test_build_order_with_a_system_and_two_strata(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "first-stratum",
                    "kind": "stratum"
                }
                ''')
        first_stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'first-stratum.morph')
        pool.add(first_stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "second-stratum",
                    "kind": "stratum"
                }
                ''')
        second_stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'second-stratum.morph')
        pool.add(second_stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "system",
                    "kind": "system",
                    "strata": [
                        "first-stratum",
                        "second-stratum"
                    ]
                }
                ''')
        system = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'system.morph')
        pool.add(system)

        order = self.graph.compute_build_order(pool)
        desired_order = collections.deque([
            [first_stratum, second_stratum],
            [system]
        ])
        self.assertEqual(order, desired_order)

        self.assertEqual(first_stratum.dependencies, [])
        self.assertEqual(second_stratum.dependencies, [])
        self.assertEqual(system.dependencies, [first_stratum, second_stratum])

    def test_detection_of_mutual_dependency_between_two_strata(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "first-stratum",
                    "kind": "stratum",
                    "build-depends": [
                        "second-stratum"
                    ]
                }
                ''')
        first_stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'first-stratum.morph')
        pool.add(first_stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "second-stratum",
                    "kind": "stratum",
                    "build-depends": [
                        "first-stratum"
                    ]
                }
                ''')
        second_stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'second-stratum.morph')
        pool.add(second_stratum)

        self.assertRaises(morphlib.buildgraph.MutualDependencyError,
                          self.graph.compute_build_order, pool)

    def test_detection_of_mutual_dependency_between_consecutive_chunks(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "first-stratum",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "first-chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "second-chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        first_stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'first-stratum.morph')
        pool.add(first_stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "second-stratum",
                    "kind": "stratum",
                    "build-depends": [
                        "first-stratum"
                    ],
                    "sources": [
                        {
                            "name": "second-chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "first-chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        second_stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'second-stratum.morph')
        pool.add(second_stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "first-chunk",
                    "kind": "chunk"
                }
                ''')
        first_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'first-chunk.morph')
        pool.add(first_chunk)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "second-chunk",
                    "kind": "chunk"
                }
                ''')
        second_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'second-chunk.morph')
        pool.add(second_chunk)

        self.assertRaises(morphlib.buildgraph.MutualDependencyError,
                          self.graph.compute_build_order, pool)

    def test_detection_of_cyclic_chunk_dependency_chain(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "first-stratum",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "first-chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "second-chunk",
                            "repo": "repo",
                            "ref": "original/ref",
                            "build-depends": [
                                "first-chunk"
                            ]
                        },
                        {
                            "name": "third-chunk",
                            "repo": "repo",
                            "ref": "original/ref",
                            "build-depends": [
                                "second-chunk"
                            ]
                        }
                    ]
                }
                ''')
        first_stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'first-stratum.morph')
        pool.add(first_stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "second-stratum",
                    "kind": "stratum",
                    "build-depends": [
                        "first-stratum"
                    ],
                    "sources": [
                        {
                            "name": "third-chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        },
                        {
                            "name": "first-chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        second_stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'second-stratum.morph')
        pool.add(second_stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "first-chunk",
                    "kind": "chunk"
                }
                ''')
        first_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'first-chunk.morph')
        pool.add(first_chunk)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "second-chunk",
                    "kind": "chunk"
                }
                ''')
        second_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'second-chunk.morph')
        pool.add(second_chunk)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "third-chunk",
                    "kind": "chunk"
                }
                ''')
        second_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph,
                'third-chunk.morph')
        pool.add(second_chunk)

        self.assertRaises(morphlib.buildgraph.CyclicDependencyChainError,
                          self.graph.compute_build_order, pool)

    def test_detection_of_chunk_dependencies_in_invalid_order(self):
        pool = morphlib.sourcepool.SourcePool()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "stratum",
                    "kind": "stratum",
                    "sources": [
                        {
                            "name": "first-chunk",
                            "repo": "repo",
                            "ref": "original/ref",
                            "build-depends": [
                                "second-chunk"
                            ]
                        },
                        {
                            "name": "second-chunk",
                            "repo": "repo",
                            "ref": "original/ref"
                        }
                    ]
                }
                ''')
        stratum = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "first-chunk",
                    "kind": "chunk"
                }
                ''')
        first_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'first-chunk.morph')
        pool.add(first_chunk)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "second-chunk",
                    "kind": "chunk"
                }
                ''')
        second_chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'second-chunk.morph')
        pool.add(second_chunk)

        self.assertRaises(morphlib.buildgraph.DependencyOrderError,
                          self.graph.compute_build_order, pool)

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
                self.repo, 'original/ref', 'sha1', morph, 'stratum.morph')
        pool.add(stratum)

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "name": "chunk",
                    "kind": "chunk"
                }
                ''')
        chunk = morphlib.source.Source(
                self.repo, 'original/ref', 'sha1', morph, 'chunk.morph')
        pool.add(chunk)

        self.assertRaises(morphlib.buildgraph.DependencyFormatError,
                          self.graph.compute_build_order, pool)
