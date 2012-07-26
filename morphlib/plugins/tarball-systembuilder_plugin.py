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


import json
import logging
import os
import shutil
import time
from collections import defaultdict
import tarfile
import traceback
import subprocess

import cliapp

import morphlib
from morphlib.artifactcachereference import ArtifactCacheReference
from morphlib.builder2 import (SystemKindBuilder, download_depends,
                               get_overlaps, log_overlaps, ldconfig,
                               write_overlap_metadata)


class RootfsTarballBuilder(SystemKindBuilder): # pragma: no cover

    system_kind = 'rootfs-tarball'

    def build_and_cache(self):
        with self.build_watch('overall-build'):
            arch = self.artifact.source.morphology['arch']
            
            rootfs_artifact = self.new_artifact(
                    self.artifact.source.morphology['name'] + '-rootfs')
            handle = self.local_artifact_cache.put(rootfs_artifact)
            image_name = handle.name

            try:
                mount_point = self.staging_area.destdir(self.artifact.source)
                factory_path = mount_point
                self.unpack_strata(factory_path)
                self.create_fstab(factory_path)
                if arch in ('arm',):
                    a = self.new_artifact(
                            self.artifact.source.morphology['name']+'-kernel')
                    with self.local_artifact_cache.put(a) as dest:
                        with open(os.path.join(factory_path,
                                               'boot',
                                               'zImage')) as kernel:
                            shutil.copyfileobj(kernel, dest)
            except BaseException, e:
                logging.error(traceback.format_exc())
                self.app.status(msg='Error while building system',
                                error=True)
                handle.abort()
                raise
    
            handle.close()

        self.save_build_times()
        return [self.artifact]
    

class RootfsTarballBuilderPlugin(cliapp.Plugin):

    def enable(self):
        self.app.system_kind_builder_factory.register(RootfsTarballBuilder)
    
    def disable(self):
        pass

