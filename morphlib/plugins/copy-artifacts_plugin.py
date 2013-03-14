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



import os
import glob
import json


import cliapp



import morphlib



class CopyArtifactsPlugin(cliapp.Plugin):

    def enable(self):
        self.app.add_subcommand(
            'list-artifacts', self.list_artifacts,
            arg_synopsis='SYSTEM')
        self.app.add_subcommand(
            'copy-artifacts', self.copy_artifacts,
            arg_synopsis='SYSTEM DESTINATION')

    def disable(self):
        pass

    def list_artifacts(self, args):
        '''List every artifact that makes up a system'''

        if len(args) != 1:
            raise cliapp.AppException(
                'Wrong number of arguments to list-artifacts command'
                '(see help)')

        system = args[0]
        artifacts = self.find_artifacts(system)
        for artifact in artifacts:
            self.app.output.write(artifact + "\n")

    def copy_artifacts(self, args):
        '''Copy every artifact that makes up a system to an rsync path'''

        if len(args) != 2:
            raise cliapp.AppException(
                'Wrong number of arguments to copy-artifacts command'
                '(see help)')

        system = args[0]
        rsync_dest = args[1]
        artifacts = self.find_artifacts(system)
        cmdline = ['rsync']
        cmdline.extend(artifacts)
        cmdline.append(rsync_dest)
        cliapp.runcmd(cmdline)

    def find_artifacts(self, system):
        artifacts_dir = os.path.join(self.app.settings['cachedir'], 'artifacts')
        artifacts = []

        def find_in_system(dirname):
            metadirs = [
                os.path.join(dirname, 'factory', 'baserock'),
                os.path.join(dirname, 'baserock')
            ]
            existing_metadirs = [x for x in metadirs if os.path.isdir(x)]
            if not existing_metadirs:
                raise NotASystemArtifactError(system)
            metadir = existing_metadirs[0]
            for basename in glob.glob(os.path.join(metadir, '*.meta')):
                metafile = os.path.join(metadir, basename)
                metadata = json.load(open(metafile))
                cache_key = metadata['cache-key']
                artifact_glob = os.path.join(artifacts_dir, cache_key) + '*'
                found_artifacts = glob.glob(artifact_glob)
                if not found_artifacts:
                    raise cliapp.AppException('Could not find cache-key '
                                              + cache_key + 'for artifact '
                                              + metajson['artifact-name'])
                artifacts.extend(found_artifacts)

        morphlib.bins.call_in_artifact_directory(
            self.app, system, find_in_system)

        return artifacts

