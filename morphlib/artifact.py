# Copyright (C) 2012, 2013, 2014  Codethink Limited
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


class Artifact(object):

    '''Represent a build result generated from a source.

    Has the following properties:

    * ``source`` -- the source from which the artifact is built
    * ``name`` -- the name of the artifact
    * ``dependents`` -- list of Sources that need this Artifact to be built

    The ``dependencies`` and ``dependents`` lists MUST be modified by
    the ``add_dependencies`` and ``add_dependent`` methods only.

    '''

    def __init__(self, source, name):
        self.source = source
        self.name = name
        # TODO: Rename to dependents when callers are changed
        self.dependent_sources = []

    def basename(self):  # pragma: no cover
        return '%s.%s' % (self.source.basename(), str(self.name))

    def metadata_basename(self, metadata_name):  # pragma: no cover
        return '%s.%s' % (self.basename(), metadata_name)

    def get_dependency_prefix_set(self):
        '''Collects all install prefixes of this artifact's build dependencies

           If any of the build dependencies of a chunk artifact are installed
           to non-standard prefixes, we need to add those prefixes to the
           PATH of the current artifact.

        '''
        result = set()
        for d in self.dependencies:
            if d.source.morphology['kind'] == 'chunk':
                result.add(d.source.prefix)
        return result

    def __str__(self):  # pragma: no cover
        return '%s|%s' % (self.source, self.name)

    def __repr__(self): # pragma: no cover
        return 'Artifact(%s)' % str(self)

    # TODO: Remove after build code stops using me
    def add_dependency(self, artifact): # pragma: no cover
        return self.source.add_dependency(artifact)
    def depends_on(self, artifact): # pragma: no cover
        return self.source.depends_on(artifact)
    @property
    def dependencies(self): # pragma: no cover
        return self.source.dependencies
    @property
    def dependents(self): # pragma: no cover
        seen = set()
        res = []
        for s in self.dependent_sources:
            for a in s.artifacts.itervalues():
                if a not in seen:
                    seen.add(a)
                    res.append(a)
        return res
    @property
    def cache_id(self): # pragma: no cover
        return self.source.cache_id
    @cache_id.setter
    def cache_id(self, v): # pragma: no cover
        assert self.source.cache_id is None or v == self.source.cache_id
        self.source.cache_id = v
    @property
    def cache_key(self): # pragma: no cover
        return self.source.cache_key
    @cache_key.setter
    def cache_key(self, v): # pragma: no cover
        assert (self.source.cache_key is None) or (v == self.source.cache_key)
        self.source.cache_key = v

    def walk(self): # pragma: no cover
        '''Return list of an artifact and its build dependencies.
        
        The artifacts are returned in depth-first order: an artifact
        is returned only after all of its dependencies.
        
        '''
        
        done = set()
        
        def depth_first(a):
            if a not in done:
                done.add(a)
                for dep in a.source.dependencies:
                    for ret in depth_first(dep):
                        yield ret
                yield a

        return list(depth_first(self))
