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
import tempfile
import gzip

import morphlib

class MountableImage(object):
    '''Mountable image (deals with decompression).

    Note, this is a read-only mount in the sense that the decompressed
    image is not then recompressed after, instead any changes are discarded.

    '''
    def __init__(self, app, artifact_path):
        self.app = app
        self.artifact_path = artifact_path

    def setup(self, path):
        self.app.status(msg='Preparing image %(path)s', path=path)
        self.app.status(msg='  Decompressing...', chatty=True)
        (tempfd, self.temp_path) = \
            tempfile.mkstemp(dir=self.app.settings['tempdir'])

        try:
            with os.fdopen(tempfd, "wb") as outfh:
                with gzip.open(path, "rb") as infh:
                    morphlib.util.copyfileobj(infh, outfh)
        except:
            os.unlink(self.temp_path)
            raise
        self.app.status(msg='  Mounting image at %(path)s',
                        path=self.temp_path, chatty=True)
        part = morphlib.fsutils.setup_device_mapping(self.app.runcmd,
                                                     self.temp_path)
        mount_point = tempfile.mkdtemp(dir=self.app.settings['tempdir'])
        morphlib.fsutils.mount(self.app.runcmd, part, mount_point)
        self.mount_point = mount_point
        return mount_point

    def cleanup(self, path, mount_point):
        self.app.status(msg='Clearing down image at %(path)s', path=path,
                        chatty=True)
        try:
            morphlib.fsutils.unmount(self.app.runcmd, mount_point)
        except:
            pass
        try:
            morphlib.fsutils.undo_device_mapping(self.app.runcmd, path)
        except:
            pass
        try:
            os.rmdir(mount_point)
            os.unlink(path)
        except:
            pass

    def __enter__(self):
        return self.setup(self.artifact_path)

    def __exit__(self, exctype, excvalue, exctraceback):
        self.cleanup(self.temp_path, self.mount_point)

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
                                      'name of output file plus two triplest')

        output = args[0]
        repo_name1, ref1, filename1 = args[1:4]
        repo_name2, ref2, filename2 = args[4:7]

        app = self.app
        build_env = morphlib.buildenvironment.BuildEnvironment(app.settings)
        ckc = morphlib.cachekeycomputer.CacheKeyComputer(build_env)
        lac, rac = morphlib.util.new_artifact_caches(app.settings)
        lrc, rrc = morphlib.util.new_repo_caches(app)

        def the_one(source, repo_name, ref, filename):
            return (source.repo_name == repo_name and
                    source.original_ref == ref and
                    source.filename == filename)

        def get_artifact(repo_name, ref, filename):
            srcpool = app.create_source_pool(
                lrc, rrc, (repo_name, ref, filename))
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

        artifact1 = get_artifact(repo_name1, ref1, filename1)
        artifact2 = get_artifact(repo_name2, ref2, filename2)

        image_path_1 = lac.get(artifact1).name
        image_path_2 = lac.get(artifact2).name

        mount_point_1 = None
        mount_point_2 = None
        with MountableImage(app, image_path_1) as mount_point_1:
            with MountableImage(app, image_path_2) as mount_point_2:
                app.runcmd(['tbdiff-create', output,
                            os.path.join(mount_point_1, 'factory'),
                            os.path.join(mount_point_2, 'factory')])
