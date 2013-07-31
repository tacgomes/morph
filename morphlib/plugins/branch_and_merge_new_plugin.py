# Copyright (C) 2012,2013  Codethink Limited
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

import morphlib


class SimpleBranchAndMergePlugin(cliapp.Plugin):

    '''Add subcommands for handling workspaces and system branches.'''

    def enable(self):
        self.app.add_subcommand('init', self.init, arg_synopsis='[DIR]')

    def disable(self):
        pass

    def init(self, args):
        '''Initialize a workspace directory.

        Command line argument:

        * `DIR` is the directory to use as a workspace, and defaults to
          the current directory.

        This creates a workspace, either in the current working directory,
        or if `DIR` is given, in that directory. If the directory doesn't
        exist, it is created. If it does exist, it must be empty.

        You need to run `morph init` to initialise a workspace, or none
        of the other system branching tools will work: they all assume
        an existing workspace. Note that a workspace only exists on your
        machine, not on the git server.

        Example:

            morph init /src/workspace
            cd /src/workspace

        '''

        if not args:
            args = ['.']
        elif len(args) > 1:
            raise morphlib.Error('init must get at most one argument')

        ws = morphlib.workspace.create(args[0])
        self.app.status(msg='Initialized morph workspace', chatty=True)

