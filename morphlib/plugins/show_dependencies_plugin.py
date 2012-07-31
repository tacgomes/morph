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


class ShowDependenciesPlugin(cliapp.Plugin):

    def enable(self):
        self.app.add_subcommand('show-dependencies',
                                self.show_dependencies,
                                arg_synopsis='(REPO REF MORPHOLOGY)...')

    def disable(self):
        pass

    def show_dependencies(self, args):
        '''Dumps the dependency tree of all input morphologies.'''

        if not os.path.exists(self.app.settings['cachedir']):
            os.mkdir(self.app.settings['cachedir'])
        cachedir = os.path.join(self.app.settings['cachedir'], 'gits')
        bundle_base_url = self.app.settings['bundle-server']
        repo_resolver = morphlib.repoaliasresolver.RepoAliasResolver(
            self.app.settings['repo-alias'])
        lrc = morphlib.localrepocache.LocalRepoCache(
            self.app, cachedir, repo_resolver, bundle_base_url)
        if self.app.settings['cache-server']:
            rrc = morphlib.remoterepocache.RemoteRepoCache(
                self.app.settings['cache-server'], repo_resolver)
        else:
            rrc = None

        # traverse the morphs to list all the sources
        for repo, ref, filename in self.app._itertriplets(args):
            pool = self.app._create_source_pool(
                lrc, rrc, (repo, ref, filename))

            resolver = morphlib.artifactresolver.ArtifactResolver()
            artifacts = resolver.resolve_artifacts(pool)

            self.app.output.write('dependency graph for %s|%s|%s:\n' %
                                  (repo, ref, filename))
            for artifact in sorted(artifacts, key=str):
                self.app.output.write('  %s\n' % artifact)
                for dependency in sorted(artifact.dependencies, key=str):
                    self.app.output.write('    -> %s\n' % dependency)

            order = morphlib.buildorder.BuildOrder(artifacts)
            self.app.output.write('build order for %s|%s|%s:\n' %
                                  (repo, ref, filename))
            for group in order.groups:
                self.app.output.write('  group:\n')
                for artifact in group:
                    self.app.output.write('    %s\n' % artifact)
