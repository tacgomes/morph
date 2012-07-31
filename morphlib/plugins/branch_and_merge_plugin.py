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


import cliapp
import os

import morphlib


class BranchAndMergePlugin(cliapp.Plugin):

    def enable(self):
        self.app.add_subcommand('init', self.init, arg_synopsis='[DIR]')
        self.app.add_subcommand('minedir', self.minedir, arg_synopsis='')

    def disable(self):
        pass

    @staticmethod
    def deduce_mine_directory():
        dirname = os.getcwd()
        while dirname != '/':
            dot_morph = os.path.join(dirname, '.morph')
            if os.path.isdir(dot_morph):
                return dirname
            dirname = os.path.dirname(dirname)
        return None

    def init(self, args):
        '''Initialize a mine.'''

        if not args:
            args = ['.']
        elif len(args) > 1:
            raise cliapp.AppException('init must get at most one argument')

        dirname = args[0]

        if os.path.exists(dirname):
            if os.listdir(dirname) != []:
                raise cliapp.AppException('can only initialize empty '
                                          'directory: %s' % dirname)
        else:
            raise cliapp.AppException('can only initialize an existing '
                                      'empty directory: %s' % dirname)

        os.mkdir(os.path.join(dirname, '.morph'))
        self.app.status(msg='Initialized morph mine', chatty=True)

    def minedir(self, args):
        '''Find morph mine directory from current working directory.'''

        dirname = self.deduce_mine_directory()
        if dirname is None:
            raise cliapp.AppException("Can't find the mine directory")
        self.app.output.write('%s\n' % dirname)
