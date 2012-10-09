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
from os.path import relpath
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


class RootfsTarballBuilder(SystemKindBuilder):  # pragma: no cover

    system_kind = 'rootfs-tarball'

    def build_and_cache(self):
        with self.build_watch('overall-build'):
            arch = self.artifact.source.morphology['arch']

            rootfs_name = self.artifact.source.morphology['name'] + '-rootfs'
            rootfs_artifact = self.new_artifact(rootfs_name)
            handle = self.local_artifact_cache.put(rootfs_artifact)

            try:
                fs_root = self.staging_area.destdir(self.artifact.source)
                self.unpack_strata(fs_root)
                self.create_fstab(fs_root)
                self.copy_kernel_into_artifact_cache(fs_root)
                unslashy_root = fs_root[1:]
                def uproot_info(info):
                    info.name = relpath(info.name, unslashy_root)
                    if info.islnk():
                        info.linkname = relpath(info.linkname,
                                                unslashy_root)
                    return info
                artiname = self.artifact.source.morphology['name']
                tar = tarfile.TarFile.gzopen(fileobj=handle, mode="w",
                                             compresslevel=1,
                                             name=artiname)
                self.app.status(msg='Constructing tarball of root filesystem',
                                chatty=True)
                tar.add(fs_root, recursive=True, filter=uproot_info)
                tar.close()
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
