# Copyright (C) 2011-2012  Codethink Limited
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


import logging
import os
import shutil
import tempfile


class Tempdir(object):

    '''Temporary file handling for morph.'''

    def __init__(self, parent=None):
        self.dirname = tempfile.mkdtemp(dir=parent)
        logging.debug('Created temporary directory %s' % self.dirname)

    def remove(self):
        '''Remove the temporary directory.'''
        logging.debug('Removing temporary directory %s' % self.dirname)
        shutil.rmtree(self.dirname)
        self.dirname = None

    def join(self, relative):
        '''Return full path to file in temporary directory.

        The relative path is given appended to the name of the
        temporary directory. If the relative path is actually absolute,
        it is forced to become relative.

        The returned path is normalized.

        '''

        return os.path.normpath(os.path.join(self.dirname, './' + relative))
