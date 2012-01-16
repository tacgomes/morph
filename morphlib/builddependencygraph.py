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
import copy
import os

import morphlib


class Node(object):

    '''Node in the dependency graph.'''

    def __init__(self, morphology):
        self.morphology = morphology
        self.dependents = []
        self.dependencies = []

    def add_dependency(self, other):
        if other not in self.dependencies:
            self.dependencies.append(other)
        if self not in other.dependents:
            other.dependents.append(self)

    def remove_dependency(self, other):
        if other in self.dependencies:
            self.dependencies.remove(other)
        if self in other.dependents:
            other.dependents.remove(self)

    def depends_on(self, other):
        return other in self.dependencies

    def __str__(self): # pragma: no cover
        return '%s (%s)' % (self.morphology.name, self.morphology.kind)

    def __deepcopy__(self, memo): # pragma: no cover
        return Node(self.morphology)


class NodeList(list):

    def __deepcopy__(self, memo): # pragma: no cover
        nodes = NodeList()
        
        old_to_new = {}
        
        for node in self:
            node_copy = copy.deepcopy(node)
            old_to_new[node] = node_copy
            nodes.append(node_copy)

        for node in self:
            node_copy = old_to_new[node]
            for dep in node.dependencies:
                dep_copy = old_to_new[dep]
                node_copy.add_dependency(dep_copy)

        return nodes


class BuildDependencyGraph(object): # pragma: no cover
    
    def __init__(self, loader, morphology):
        self.loader = loader
        self.morphology = morphology
        self.nodes = None

    def add(self, morphology):
        node = Node(morphology)
        if node not in self.nodes:
            self.nodes.append(node)

    def resolve(self):
        self.cached_morphologies = {}
        self._resolve_strata()
        self._resolve_chunks()

    def build_order(self):
        sorting = self._compute_topological_sorting()

        #print
        #print 'sorting: %s' % [str(x) for x in sorting]
        #print

        groups = []
        group_nodes = {}

        group = []
        groups.append(group)

        for node in sorting:
            create_group = False
            for dep in node.dependencies:
                if dep in group:
                    create_group = True

            if create_group:
                group = []
                groups.append(group)

            group.append(node)

        morphology_groups = []
        for group in groups:
            morphology_group = []
            for node in group:
                morphology_group.append(node.morphology)
            morphology_groups.append(morphology_group)

        return morphology_groups

    def _resolve_strata(self):
        self.nodes = NodeList()

        if self.morphology.kind == 'stratum':
            root = Node(self.morphology)
            self.nodes.append(root)

            queue = collections.deque()
            queue.append(root)
            while len(queue) > 0:
                node = queue.popleft()

                if not node.morphology.build_depends:
                    continue
                
                if isinstance(node.morphology.build_depends, list):
                    for other_name in node.morphology.build_depends:
                        # prepare a tuple for loading the morphology
                        repo = node.morphology.repo
                        ref = node.morphology.ref
                        filename = '%s.morph' % other_name
                        info = (repo, ref, filename)

                        # look up or create a node for the morphology
                        other_node = self.cached_morphologies.get(info, None)
                        if not other_node:
                            #print other_name
                            morphology = self.loader.load(repo, ref, filename)
                            other_node = Node(morphology)

                            # cache the node for this morphology
                            self.cached_morphologies[info] = other_node

                        # add the morphology node to the graph
                        node.add_dependency(other_node)
                        self.nodes.append(other_node)
                        queue.append(other_node)
                else:
                    raise Exception('%s  uses an invalid "build-depends" format' % 
                                    os.path.basename(stratum_node.morphology.filename))

        #print 'strata: %s' % [str(x) for x in self.nodes]

    def _resolve_chunks(self):
        strata_nodes = list(self.nodes)
        for stratum_node in strata_nodes:
            self._resolve_stratum_chunks(stratum_node)

    def _morphology_node(self, repo, ref, filename):
        info = (repo, ref, filename)
        
        if info in self.cached_morphologies:
            return self.cached_morphologies[info]
        else:
            morphology = self.loader.load(repo, ref, filename)
            node = Node(morphology)
            self.nodes.append(node)
            self.cached_morphologies[info] = node
            return node

    def _resolve_stratum_chunks(self, stratum_node):
        stratum_chunk_nodes = []
        chunk_lookup = {}

        # second, create nodes for all chunks in the stratum
        for i in xrange(0, len(stratum_node.morphology.sources)):
            source = stratum_node.morphology.sources[i]

            # construct the build tuple
            repo = source['repo']
            ref = source['ref']
            filename = '%s.morph' % (source['morph']
                                     if 'morph' in source
                                     else source['name'])

            chunk_node = self._morphology_node(repo, ref, filename)

            chunk_lookup[source['name']] = chunk_node

            stratum_chunk_nodes.append(chunk_node)

            # read the build-depends information
            build_depends = (source['build-depends']
                             if 'build-depends' in source
                             else None)

            # turn build-depends into proper dependencies in the graph
            if build_depends is None:
                for j in xrange(0, i):
                    chunk_node.add_dependency(stratum_chunk_nodes[j])
            elif isinstance(build_depends, list):
                for depname in build_depends:
                    if depname in chunk_lookup:
                        depnode = chunk_lookup[depname]
                        chunk_node.add_dependency(depnode)
                    else:
                        raise Exception('%s: source "%s" references "%s" '
                                        'before it is defined' % 
                                        (os.path.basename(stratum_node.morphology.filename),
                                         source['name'],
                                         depname))
            else:
                raise Exception('%s: source "%s" uses an invalid '
                                '"build-depends" format' % 
                                (os.path.basename(stratum_node.morphology.filename),
                                 source['name']))

        # make the chunk nodes in this stratum depend on all strata
        # that need to be built first
        for chunk_node in stratum_chunk_nodes:
            for stratum_dep in stratum_node.dependencies:
                chunk_node.add_dependency(stratum_dep)

        # clear the dependencies of the stratum
        stratum_node.dependencies = []

        # make the stratum node depend on all its chunk nodes
        for chunk_node in stratum_chunk_nodes:
            stratum_node.add_dependency(chunk_node)

    def _compute_topological_sorting(self):
        nodes = copy.deepcopy(self.nodes)

        original_node = {}
        for node in self.nodes:
            for node_copy in nodes:
                if node.morphology == node_copy.morphology:
                    original_node[node_copy] = node

        #print 'compute topological sorting:'
        #print '  nodes: %s' % [str(x) for x in nodes]

        sorting = []
        leafs = collections.deque()
        
        for node in nodes:
            if len(node.dependencies) is 0:
                leafs.append(node)

        #print '  leafs: %s' % [str(x) for x in leafs]

        while len(leafs) > 0:
            leaf = leafs.popleft()
            sorting.append(leaf)

            #print '  visit %s' % leaf

            #print '  visit %s' % leaf

            for parent in list(leaf.dependents):
                #print '    parent %s' % parent
                #print '    parent %s dependencies: %s' % (parent, [str(x) for x in parent.dependencies])
                parent.remove_dependency(leaf)
                #print '    parent %s dependencies: %s' % (parent, [str(x) for x in parent.dependencies])
                if len(parent.dependencies) == 0:
                    #print '    add %s' % parent
                    leafs.append(parent)

        #print [str(node) for node in sorting]
        if len(sorting) < len(nodes):
            raise Exception('Cyclic dependencies found in the dependency '
                            'graph of "%s"' % self.morphology)

        #return sorting
        return [original_node[node] for node in sorting]
