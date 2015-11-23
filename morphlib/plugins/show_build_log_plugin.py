# Copyright (C) 2015 Codethink Limited
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


import cliapp
import logging
import os
import urllib
import urlparse

import morphlib


class ShowBuildLog(cliapp.Plugin):

    def enable(self):
        self.app.add_subcommand('show-build-log', self.show_build_log,
                                arg_synopsis='SYSTEM CHUNK')

    def disable(self):
        pass

    def show_build_log(self, args):
        '''Display build logs for a given component in a system.

        Command line arguments:

        * `SYSTEM` is the name of the system we want log data from.
        * `CHUNK` is the name of the chunk we want log data for.

        Example:

            morph show-build-log devel-system-x86_64-generic.morph pip

        '''

        if len(args) != 2:
            raise cliapp.AppException('show-build-log expects system filename '
                                      'and chunk as input.')

        system = args[0]
        chunk = args[1]

        # Hack to allow getting build log of chunks for a different
        # architecture
        def validate(self, root_artifact):
            pass
        morphlib.buildcommand.BuildCommand._validate_architecture = validate

        definitions_repo = morphlib.definitions_repo.open(
            '.', search_for_root=True, app=self.app)
        source_pool_context = definitions_repo.source_pool(
            ref=definitions_repo.HEAD, system_filename=system)
        with source_pool_context as source_pool:
            build_command = morphlib.buildcommand.BuildCommand(self.app, None)
            root = build_command.resolve_artifacts(source_pool)

            arch = root.source.morphology['arch']
            build_env = build_command.new_build_env(arch)

            ckc = morphlib.cachekeycomputer.CacheKeyComputer(build_env)

            cache_key = None
            for source in set(a.source for a in root.walk()):
                if source.name == chunk:
                    cache_key = ckc.compute_key(source)
                    break

            if cache_key:
                f = self.get_build_log_for_artifact(cache_key)
                build_output = []
                for line in f:
                    build_output.append(str(line))
                self.app.output.write(''.join(build_output))
            else:
                raise cliapp.AppException('Component not found in the given '
                                          'system.')

    def get_build_log_for_artifact(self, cache_key):
        lac, rac = morphlib.util.new_artifact_caches(self.app.settings)

        if lac.has_source_metadata(None, cache_key, 'build-log'):
            logging.info('Found build log for %s in local cache.', cache_key)
            f = lac.get_source_metadata(None, cache_key, 'build-log')
        else:
            artifact_cache_server = (
                self.app.settings['artifact-cache-server'] or
                self.app.settings['cache-server'])

            url = urlparse.urljoin(artifact_cache_server,
                '/1.0/artifacts?filename=%s.build-log' % cache_key)
            response = urllib.urlopen(url)
            if response.getcode() == 200:
                logging.info('Found build log for %s in remote cache %s.',
                             cache_key, artifact_cache_server)
                f = response
            elif response.getcode() == 404:
                raise cliapp.AppException(
                    'No build log for artifact %s found on cache server %s' %
                    (cache_key, artifact_cache_server))
            else:
                raise cliapp.AppException(
                    'Error connecting to cache server %s: %s' %
                    (artifact_cache_server, response.getcode()))

        return f
