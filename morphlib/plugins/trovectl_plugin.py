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
        self.app.add_subcommand(
            'trovectl', self.trovectl, arg_synopsis='GITANO-COMMAND [ARG...]')

    def disable(self):
        pass

    def trovectl(self, args, **kwargs):
        '''Invoke Gitano commands on the Trove host.

        Command line arguments:

        * `GITANO-COMMAND` is the Gitano command to invoke on the Trove.
        * `ARG` is a Gitano command argument.

        This invokes Gitano commands on the Trove host configured
        in the Morph configuration (see `--trove-host`).

        Trove is the Codethink code hosting appliance. Gitano is the
        git server management component of that.

        Example:

            morph trovectl whoami
            morph trovectl help

        '''

        trove = 'git@' + self.app.settings['trove-host']
        self.app.runcmd(['ssh', trove] + args,
            stdin=None, stdout=None, stderr=None)

