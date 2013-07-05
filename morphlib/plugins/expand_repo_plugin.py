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

import morphlib


class ExpandRepoPlugin(cliapp.Plugin):

    '''Expand an aliased repo URL to be unaliases.'''

    def enable(self):
        self.app.add_subcommand(
            'expand-repo', self.expand_repo, arg_synopsis='[REPOURL...]')

    def disable(self):
        pass

    def expand_repo(self, args):
        '''Expand repo aliases in URLs.

        Command line arguments:

        * `REPOURL` is a URL that may or may not be using repository
          aliases.

        See the `--repo-alias` option for more about repository aliases.

        Example:

            $ morph expand-repo baserock:baserock/morphs
            Original: baserock:baserock/morphs
            pull: git://trove.baserock.org/baserock/baserock/morphs
            push: ssh://git@git.baserock.org/baserock/baserock/morphs

        '''

        aliases = self.app.settings['repo-alias']
        resolver = morphlib.repoaliasresolver.RepoAliasResolver(aliases)
        for repourl in args:
            self.app.output.write(
                'Original: %s\npull: %s\npush: %s\n\n' %
                    (repourl,
                     resolver.pull_url(repourl),
                     resolver.push_url(repourl)))

