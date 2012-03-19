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
import os

import morphlib


class BuildDependencyGraph(object): # pragma: no cover

    '''This class constructs a build dependency graph from an input morphology.

    Given a chunk, stratum or system morphology, this class constructs a build
    dependency graph and provides ways to traverse it. It also provides a 
    method to transform the dependency graph into groups of items that are 
    independent and can be built in parallel.
    
    '''
    
    def __init__(self, source_manager, morph_loader, repo, ref, filename):
        self.source_manager = source_manager
        self.morph_loader = morph_loader
        self.root_repo = repo
        self.root_ref = ref
        self.root_filename = filename
        self.blobs = set()

    def create_blob(self, treeish, filename):
        '''Creates a blob from a morphology.'''

        morph = self.morph_loader.load(treeish, filename)

        if morph.kind == 'stratum':
            return morphlib.blobs.Stratum(morph)
        elif morph.kind == 'chunk':
            return morphlib.blobs.Chunk(morph)
        else:
            return morphlib.blobs.System(morph)

    def get_blob(self, treeish, filename):
        '''Takes a repo, ref, filename and looks up the blob for them.

        Loads the corresponding morphology and chunk/stratum/system object
        on-demand if it is not cached yet.
           
        '''

        key = (treeish, filename)
        blob = self.cached_blobs.get(key, None)
        if not blob:
            blob = self.create_blob(treeish, filename)
            self.cached_blobs[key] = blob
        return blob

    def resolve(self):
        '''Constructs the graph by resolving dependencies recursively.'''

        self.cached_blobs = {}
        self.blobs = set()

        root = self.resolve_root()
        self.resolve_strata()
        self.resolve_chunks()
        return root

    def resolve_root(self):
        # prepare the repo, load the morphology and blob information
        treeish = self.source_manager.get_treeish(self.root_repo,
                                                  self.root_ref)
        root = self.get_blob(treeish, self.root_filename)
        self.blobs.add(root)

        # load all strata the morph depends on (only if it's a system image)
        if root.morph.kind == 'system':
            for stratum_name in root.morph.strata:
                filename = '%s.morph' % stratum_name
                stratum = self.get_blob(treeish, filename)
                root.add_dependency(stratum)
                stratum.add_parent(root)
                self.blobs.add(stratum)

        return root

    def resolve_strata(self):
        '''Generates a dependency graph of strata recursively.

        It starts with the input morphology and attempts to resolve all its
        build dependencies recursively using breadth-first search. Morphologies
        and blobs are loaded from disk on demand.
           
        '''

        # start the BFS at all input strata
        queue = collections.deque()
        strata = [x for x in self.blobs if x.morph.kind == 'stratum']
        queue.extend(strata)
        
        while len(queue) > 0:
            stratum = queue.popleft()

            # the DFS recursion ends whenever we have a stratum
            # that depends on nothing else
            if not stratum.morph.build_depends:
                continue
            
            # verify that the build-depends format is valid
            if isinstance(stratum.morph.build_depends, list):
                for depname in stratum.morph.build_depends:
                    # load the dependency stratum on demand
                    depstratum = self.get_blob(stratum.morph.treeish,
                                               '%s.morph' % depname)
                    self.blobs.add(depstratum)

                    # add the dependency stratum to the graph
                    stratum.add_dependency(depstratum)
                    queue.append(depstratum)
            else:
                raise Exception('%s uses an invalid "build-depends" format'
                                % stratum)

    def resolve_chunks(self):
        '''Resolves all chunks of the strata and inserts them into the graph.
        
        Starting with a dependency graph of strata, this method fills the
        graph with all contained chunks and creates dependencies where 
        appropriate. Chunk morphologies and blobs are loaded on demand.
        
        '''

        blobs = list(self.blobs)
        for blob in blobs:
            if isinstance(blob, morphlib.blobs.Stratum):
                self.resolve_stratum_chunks(blob)

    def resolve_stratum_chunks(self, stratum):
        # the set of chunks contained in the stratum
        stratum_chunks = set()

        # dictionary that maps chunk names to chunks
        name_to_chunk = {}

        # create objects for all chunks in the stratum
        for i in xrange(0, len(stratum.morph.sources)):
            source = stratum.morph.sources[i]

            # construct a tuple for loading the chunk
            repo = source['repo']
            ref = source['ref']
            filename = '%s.morph' % (source['morph']
                                     if 'morph' in source
                                     else source['name'])

            # load the chunk on demand
            treeish = self.source_manager.get_treeish(repo, ref)
            chunk = self.get_blob(treeish, filename)
            chunk.add_parent(stratum)

            # store (name -> chunk) association to avoid loading the chunk 
            # twice
            name_to_chunk[source['name']] = chunk

            # read the build-depends information
            build_depends = (source['build-depends']
                             if 'build-depends' in source
                             else None)

            # turn build-depends into proper dependencies in the graph
            if build_depends is None:
                # chunks with no build-depends implicitly depend on all
                # chunks listed earlier in the same stratum
                for dependency in stratum_chunks:
                    if not dependency is chunk:
                        chunk.add_dependency(dependency)
            elif isinstance(build_depends, list):
                for depname in build_depends:
                    if depname in name_to_chunk:
                        dependency = name_to_chunk[depname]
                        if not dependency is chunk:
                            chunk.add_dependency(dependency)
                    else:
                        raise Exception('%s: source %s references %s before '
                                        'it is defined' % 
                                                       (stratum.morph.filename,
                                                        source['name'],
                                                        depname))
            else:
                raise Exception('%s: source %s uses an invalid build-depends '
                                'format' %
                                (stratum.morph.filename, source['name']))
            
            # add the chunk to stratum and graph
            stratum_chunks.add(chunk)
            self.blobs.add(chunk)

        # make the chunks in this stratum depend on all
        # strata that need to be built first
        for chunk in stratum_chunks:
            for dependency in stratum.dependencies:
                chunk.add_dependency(dependency)

        ## clear the dependencies of the stratum
        #for dependency in set(stratum.dependencies):
        #    stratum.remove_dependency(dependency)

        # make the stratum depend on all its chunks
        for chunk in stratum_chunks:
            stratum.add_dependency(chunk)

    def build_order(self):
        '''Returns a queue of build groups in a valid order.
        
        This function computes a topological sorting of the dependency graph
        and generates a deque of groups, each of which contains a set of items
        that are independent and can be built in parallel. The items in each
        group are guaranteed to depend only on items in previous groups.
        
        '''

        sorting = self.compute_topological_sorting()
        groups = collections.deque()

        # create the first group
        group = set()
        groups.append(group)

        # traverse the graph in topological order
        for blob in sorting:
            # add the current item to the current group, or a new group
            # if one of its dependencies is in the current one
            create_group = False
            for dependency in blob.dependencies:
                if dependency in group:
                    create_group = True
            if create_group:
                group = set()
                groups.append(group)
            group.add(blob)

        # return the set of blobs and the build groups
        return set(self.blobs), groups

    def compute_topological_sorting(self):
        '''Computes a topological sorting of the dependency graph. 
        
        A topological sorting basically is the result of a series of
        breadth-first searches starting at each leaf node (blobs with no
        dependencies). Blobs are added to the sorting as soon as all their
        dependencies have been added (which means that by then, all
        dependencies are satisfied).

        For more information, see
        http://en.wikipedia.org/wiki/Topological_sorting.
        
        '''

        # map blobs to sets of satisfied dependencies. this is to detect when
        # we can actually add blobs to the BFS queue. rather than dropping
        # links between nodes, like most topological sorting algorithms do,
        # we simply remember all satisfied dependencies and check if all
        # of them are met repeatedly
        satisfied_dependencies = {}

        # create an empty sorting
        sorting = collections.deque()

        # create a set of leafs to start the DFS from
        leafs = collections.deque()
        for blob in self.blobs:
            satisfied_dependencies[blob] = set()
            if len(blob.dependencies) == 0:
                leafs.append(blob)

        while len(leafs) > 0:
            # fetch a leaf blob from the DFS queue
            blob = leafs.popleft()

            # add it to the sorting
            sorting.append(blob)

            # mark this dependency as resolved
            for dependent in blob.dependents:
                satisfied_dependencies[dependent].add(blob)

                # add the dependent blob as a leaf if all
                # its dependencies have been resolved
                has = len(satisfied_dependencies[dependent])
                needs = len(dependent.dependencies)
                if has == needs:
                    leafs.append(dependent)

        # if not all dependencies were resolved on the way, we
        # have found at least one cyclic dependency
        if len(sorting) < len(self.blobs):
            raise Exception('Cyclic dependencies found in the dependency '
                            'graph of %s|%s|%s' % 
                            (self.root_repo, 
                             self.root_ref,
                             self.root_filename))

        return sorting
