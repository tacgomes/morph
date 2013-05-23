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

import cliapp

import morphlib

class TrovectlPlugin(cliapp.Plugin):

    def enable(self):
        self.app.add_subcommand('trovectl', self.trovectl)

    def disable(self):
        pass

    def trovectl(self, args, **kwargs):
        trove = 'git@' + self.app.settings['trove-host']
        self.app.runcmd(['ssh', trove] + args,
            stdout=None, stderr=None)

