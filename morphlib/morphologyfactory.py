#!/usr/bin/python
#
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

import morphlib
import cliapp

class MorphologyFactoryError(cliapp.AppException):
    pass

class AutodetectError(MorphologyFactoryError):
    def __init__(self, repo_name, ref):
        MorphologyFactoryError.__init__(self, 
                "Failed to determine the build system of repo %s at "
                "ref %s" % (repo_name, ref))

class MorphologyFactory(object):
    '''An way of creating morphologies which will provide a default'''

    def __init__(self, local_repo_cache, remote_repo_cache):
        self._lrc = local_repo_cache
        self._rrc = remote_repo_cache

    def get_morphology(self, reponame, sha1, filename):
        try:
            text = self._cat_text(reponame, sha1, filename)
        except:
            text = self._autodetect_text(reponame, sha1, filename)
        return morphlib.morph2.Morphology(text)

    def _cat_text(self, reponame, sha1, filename):
        if self._lrc.has_repo(reponame):
            repo = self._lrc.get_repo(reponame)
            return repo.cat(sha1, filename)
        else:
            return self._rrc.cat_file(reponame, sha1, filename)

    def _autodetect_text(self, reponame, sha1, filename):
        if self._lrc.has_repo(reponame):
            repo = self._lrc.get_repo(reponame)
            files = repo.list_files(sha1)
        else:
            files = self._rrc.list_files(reponame, sha1)
        bs = morphlib.buildsystem.detect_build_system(lambda x: x in files)
        if bs is None:
            raise AutodetectError(reponame, sha1)
        assert filename.endswith('.morph')
        morph_name = filename[:-len('.morph')]
        morph_text = bs.get_morphology_text(morph_name)
        return morph_text
