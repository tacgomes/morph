# Copyright (C) 2013  Codethink Limited
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
#
# =*= License: GPL-2 =*=


import morphlib


class StratumNotInSystemError(morphlib.Error):

    def __init__(self, system_name, stratum_name):
        self.msg = (
            'System %s does not contain %s' % (system_name, stratum_name))


class StratumNotInSetError(morphlib.Error):

    def __init__(self, stratum_name):
        self.msg = 'Stratum %s is not in MorphologySet' % stratum_name


class ChunkNotInStratumError(morphlib.Error):

    def __init__(self, stratum_name, chunk_name):
        self.msg = (
            'Stratum %s does not contain %s' % (stratum_name, chunk_name))


class MorphologySet(object):

    '''Store and manipulate a set of Morphology objects.'''

    def __init__(self):
        self.morphologies = []

    def add_morphology(self, morphology):
        '''Add a morphology object to the set, unless it's there already.'''

        triplet = (
            morphology.repo_url,
            morphology.ref,
            morphology.filename
        )
        for existing in self.morphologies:
            existing_triplet = (
                existing.repo_url,
                existing.ref,
                existing.filename
            )
            if existing_triplet == triplet:
                return

        self.morphologies.append(morphology)

    def has(self, repo_url, ref, filename):
        '''Does the set have a morphology for the given triplet?'''
        return self._get_morphology(repo_url, ref, filename) is not None

    def _get_morphology(self, repo_url, ref, filename):
        for m in self.morphologies:
            if (m.repo_url == repo_url and
                m.ref == ref and
                m.filename == filename):
                return m
        return None

    def _find_spec(self, specs, wanted_name):
        for spec in specs:
            name = spec.get('morph', spec.get('name'))
            if name == wanted_name:
                return spec['repo'], spec['ref'], name
        return None, None, None

    def get_stratum_in_system(self, system_morph, stratum_name):
        '''Return morphology for a stratum that is in a system.

        If the stratum is not in the system, raise StratumNotInSystemError.
        If the stratum morphology has not been added to the set,
        raise StratumNotInSetError.

        '''

        repo_url, ref, morph = self._find_spec(
            system_morph['strata'], stratum_name)
        if repo_url is None:
            raise StratumNotInSystemError(system_morph['name'], stratum_name)
        m = self._get_morphology(repo_url, ref, '%s.morph' % morph)
        if m is None:
            raise StratumNotInSetError(stratum_name)
        return m

    def get_chunk_triplet(self, stratum_morph, chunk_name):
        '''Return the repo url, ref, morph name triplet for a chunk.

        Given a stratum morphology, find the triplet used to refer to
        a given chunk. Note that because of how the chunk may be
        referred to using either name or morph fields in the morphology,
        the morph field (or its computed value) is always returned.
        Note also that the morph field, not the filename, is returned.

        Raise ChunkNotInStratumError if the chunk is not found in the
        stratum.

        '''

        repo_url, ref, morph = self._find_spec(
            stratum_morph['chunks'], chunk_name)
        if repo_url is None:
            raise ChunkNotInStratumError(stratum_morph['name'], chunk_name)
        return repo_url, ref, morph

    def change_ref(self, repo_url, orig_ref, morph_filename, new_ref):
        '''Change a triplet's ref to a new one in all morphologies in a ref.

        Change orig_ref to new_ref in any morphology that references the
        original triplet. This includes stratum build-dependencies.

        '''

        def wanted_spec(spec):
            return (spec['repo'] == repo_url and
                    spec['ref'] == orig_ref and
                    spec['morph'] + '.morph' == morph_filename)

        def change_specs(specs, m):
            for spec in specs:
                if wanted_spec(spec):
                    spec['ref'] = new_ref
                    m.dirty = True

        def change(m):
            if m['kind'] == 'system':
                change_specs(m['strata'], m)
            elif m['kind'] == 'stratum':
                change_specs(m['chunks'], m)
                change_specs(m['build-depends'], m)

        for m in self.morphologies:
            change(m)

        m = self._get_morphology(repo_url, orig_ref, morph_filename)
        if m and m.ref != new_ref:
            m.ref = new_ref
            m.dirty = True

