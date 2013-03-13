# Copyright (C) 2012-2013  Codethink Limited
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
import tempfile
import gzip

import morphlib

from morphlib.mountableimage import MountableImage


class TrebuchetPlugin(cliapp.Plugin):

    def enable(self):
        self.app.add_subcommand('make-patch',
                                self.make_patch,
                                arg_synopsis='PATH SRC_TRIPLE TGT_TRIPLE')

    def disable(self):
        pass

    def make_patch(self, args):
        '''Create a Trebuchet patch between two system images.'''

        if len(args) != 7:
            raise cliapp.AppException('make-patch requires arguments: '
                                      'name of output file plus two triplets')

        output = args[0]
        repo_name1, ref1, filename1 = args[1:4]
        repo_name2, ref2, filename2 = args[4:7]

        app = self.app
        lac, rac = morphlib.util.new_artifact_caches(app.settings)
        lrc, rrc = morphlib.util.new_repo_caches(app)

        def get_system_source(repo_name, ref, filename):
            srcpool = app.create_source_pool(
                lrc, rrc, (repo_name, ref, filename))
            src = srcpool.lookup(repo_name, ref, filename)
            return srcpool, src.morphology['arch']

        srcpool1, arch1 = get_system_source(repo_name1, ref1, filename1)
        srcpool2, arch2 = get_system_source(repo_name2, ref2, filename2)

        if arch1 != arch2:
            raise cliapp.AppException('System architectures do not match: '
                                      '%s vs. %s' % (arch1, arch2))

        build_env = morphlib.buildenvironment.BuildEnvironment(
            app.settings, arch1)
        ckc = morphlib.cachekeycomputer.CacheKeyComputer(build_env)

        def the_one(source, repo_name, ref, filename):
            return (source.repo_name == repo_name and
                    source.original_ref == ref and
                    source.filename == filename)

        def get_artifact(srcpool, repo_name, ref, filename):
            ar = morphlib.artifactresolver.ArtifactResolver()
            artifacts = ar.resolve_artifacts(srcpool)
            for artifact in artifacts:
                artifact.cache_key = ckc.compute_key(artifact)
                if the_one(artifact.source, repo_name, ref, filename):
                    a = morphlib.artifact.Artifact(
                        artifact.source,
                        artifact.source.morphology['name'] + '-rootfs')
                    a.cache_key = artifact.cache_key
                    return a

        artifact1 = get_artifact(srcpool1, repo_name1, ref1, filename1)
        artifact2 = get_artifact(srcpool2, repo_name2, ref2, filename2)

        image_path_1 = lac.get(artifact1).name
        image_path_2 = lac.get(artifact2).name

        mount_point_1 = None
        mount_point_2 = None
        with MountableImage(app, image_path_1) as mount_point_1:
            with MountableImage(app, image_path_2) as mount_point_2:
                app.runcmd(['tbdiff-create', output,
                            os.path.join(mount_point_1, 'factory'),
                            os.path.join(mount_point_2, 'factory')])
