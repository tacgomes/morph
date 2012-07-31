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


class UpdateGitsPlugin(cliapp.Plugin):

    def enable(self):
        self.app.add_subcommand('update-gits',
                                self.update_gits,
                                arg_synopsis='(REPO REF MORPHOLOGY)...')

    def disable(self):
        pass

    def update_gits(self, args):
        '''Update cached git repositories.

        Parse the given morphologies, and their dependencies, and
        update all the git repositories referred to by them in the
        morph cache directory.

        '''

        app = self.app
        if not os.path.exists(app.settings['cachedir']):
            os.mkdir(app.settings['cachedir'])
        cachedir = os.path.join(app.settings['cachedir'], 'gits')
        repo_resolver = morphlib.repoaliasresolver.RepoAliasResolver(
            app.settings['repo-alias'])
        bundle_base_url = app.settings['bundle-server']
        cache = morphlib.localrepocache.LocalRepoCache(
            app, cachedir, repo_resolver, bundle_base_url)

        subs_to_process = set()

        def visit(reponame, ref, filename, absref, morphology):
            app.status(msg='Updating %(repo_name)s %(ref)s %(filename)s',
                       repo_name=reponame, ref=ref, filename=filename)
            assert cache.has_repo(reponame)
            cached_repo = cache.get_repo(reponame)
            try:
                submodules = morphlib.git.Submodules(app, cached_repo.path,
                                                     absref)
                submodules.load()
            except morphlib.git.NoModulesFileError:
                pass
            else:
                for submod in submodules:
                    subs_to_process.add((submod.url, submod.commit))

        app.traverse_morphs(app.itertriplets(args), cache, None,
                            update=True, visit=visit)

        done = set()
        for url, ref in subs_to_process:
            app.cache_repo_and_submodules(cache, url, ref, done)
