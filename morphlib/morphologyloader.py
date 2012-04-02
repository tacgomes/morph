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


import StringIO

import morphlib


class MorphologyLoader(object):

    '''Load morphologies from git and parse them into Morphology objects.'''

    def __init__(self, settings):
        self.settings = settings
        self.morphologies = {}

    def load(self, treeish, filename, chunk_name=None):
        key = (treeish, filename)
        if key in self.morphologies:
            return self.morphologies[key]
        else:
            try:
                morph = self._get_morph_from_git(treeish, filename)
            except morphlib.execute.CommandFailure: # pragma: no cover
                morph = None
            if morph is None and chunk_name is not None: # pragma: no cover
                morph = self._autodetect_morph(treeish, filename, chunk_name)
            if morph is None: # pragma: no cover
                raise Exception("Can't find morphology %s" % filename)
            self.morphologies[key] = morph
            return morph

    def _autodetect_morph(self, treeish, filename, chunk): # pragma: no cover
        def exists(x):
            try:
                self._get_morph_text(treeish, x)
            except morphlib.execute.CommandFailure:
                return False
            else:
                return True
        bs = morphlib.buildsystem.detect_build_system(exists)
        if bs is not None:
            morph_text = bs.get_morphology_text(chunk)
            return self._get_morph(treeish, filename, morph_text)
        else:
            return None

    def _get_morph_text(self, treeish, filename): # pragma: no cover
        return morphlib.git.get_morph_text(treeish, filename)

    def _get_morph_from_git(self, treeish, filename):
        morph_text = self._get_morph_text(treeish, filename)
        return self._get_morph(treeish, filename, morph_text)

    def _get_morph(self, treeish, filename, morph_text):
        fp = StringIO.StringIO(morph_text)
        fp.name = filename
        return morphlib.morphology.Morphology(treeish, fp)

