# Copyright (C) 2013-2015  Codethink Limited
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
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# =*= License: GPL-2 =*=


import cliapp

import morphlib


class MorphologyFinder(object):

    '''Abstract away finding morphologies in a git repository.

    This class provides an abstraction layer between a git repository
    and the morphologies contained in it.

    '''

    def __init__(self, gitdir, ref=None):
        self.gitdir = gitdir
        self.ref = ref

    def read_file(self, filename):
        '''Return the text of a file inside the Git repo.'''
        return self.gitdir.read_file(filename, self.ref)

    def list_morphologies(self):
        '''Return the filenames of all morphologies in the (repo, ref).

        Finds all morphologies in the git directory at the specified
        ref.

        '''

        def is_morphology_path(path):
            return path.endswith('.morph')

        return (path
                for path in self.gitdir.list_files(self.ref)
                if is_morphology_path(path))
