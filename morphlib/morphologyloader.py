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


import os
import StringIO
import urlparse

import morphlib


class MorphologyLoader(object):

    '''Load morphologies from git and parse them into Morphology objects.'''

    def __init__(self, settings):
        self.settings = settings
        self.morphologies = {}

    def load(self, repo, ref, filename):
        base_url = self.settings['git-base-url']
        if not base_url.endswith('/'):
            base_url += '/'
        repo = urlparse.urljoin(base_url, repo)

        key = (repo, ref, filename)
        
        if key in self.morphologies:
            return self.morphologies[key]
        else:
            morph = self._get_morph_from_git(repo, ref, filename)
            self.morphologies[key] = morph
            return morph

    def _get_morph_text(self, repo, ref, filename): # pragma: no cover
        return morphlib.git.get_morph_text(repo, ref, filename)

    def _get_morph_from_git(self, repo, ref, filename):
        morph_text = self._get_morph_text(repo, ref, filename)
        scheme, netlock, path, params, query, frag = urlparse.urlparse(repo)
        f = StringIO.StringIO(morph_text)
        f.name = os.path.join(path, filename)
        morph = morphlib.morphology.Morphology(repo, ref, f,
                                               self.settings['git-base-url'])
        return morph
