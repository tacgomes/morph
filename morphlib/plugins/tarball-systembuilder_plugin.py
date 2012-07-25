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
                self._unpack_strata(factory_path)
                self._create_fstab(factory_path)
                if arch in ('x86', 'x86_64'):
                    self._create_extlinux_config(factory_path)
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

    def _unpack_strata(self, path):
        self.app.status(msg='Unpacking strata to %(path)s',
                        path=path, chatty=True)
        with self.build_watch('unpack-strata'):
            # download the stratum artifacts if necessary
            download_depends(self.artifact.dependencies,
                             self.local_artifact_cache,
                             self.remote_artifact_cache,
                             ('meta',))

            # download the chunk artifacts if necessary
            for stratum_artifact in self.artifact.dependencies:
                f = self.local_artifact_cache.get(stratum_artifact)
                chunks = [ArtifactCacheReference(a) for a in json.load(f)]
                download_depends(chunks,
                                 self.local_artifact_cache,
                                 self.remote_artifact_cache)
                f.close()

            # check whether the strata overlap
            overlaps = get_overlaps(self.artifact, self.artifact.dependencies,
                                    self.local_artifact_cache)
            if len(overlaps) > 0:
                self.app.status(msg='Overlaps in system artifact '
                                    '%(artifact_name)s detected',
                                artifact_name=self.artifact.name,
                                error=True)
                log_overlaps(overlaps)
                write_overlap_metadata(self.artifact, overlaps,
                                       self.local_artifact_cache)

            # unpack it from the local artifact cache
            for stratum_artifact in self.artifact.dependencies:
                f = self.local_artifact_cache.get(stratum_artifact)
                for chunk in (ArtifactCacheReference(a) for a in json.load(f)):
                    self.app.status(msg='Unpacking chunk %(basename)s',
                                    basename=chunk.basename(), chatty=True)
                    chunk_handle = self.local_artifact_cache.get(chunk)
                    morphlib.bins.unpack_binary_from_file(chunk_handle, path)
                    chunk_handle.close()
                f.close()
                meta = self.local_artifact_cache.get_artifact_metadata(
                                                      stratum_artifact, 'meta')
                dst = morphlib.savefile.SaveFile(
                        os.path.join(path, 'baserock',
                                     '%s.meta' % stratum_artifact.name), 'w')
                shutil.copyfileobj(meta, dst)
                dst.close()
                meta.close()

            ldconfig(self.app.runcmd, path)

    def _create_fstab(self, path):
        self.app.status(msg='Creating fstab in %(path)s',
                        path=path, chatty=True)
        with self.build_watch('create-fstab'):
            fstab = os.path.join(path, 'etc', 'fstab')
            if not os.path.exists(os.path.dirname(fstab)):# FIXME: should exist
                os.makedirs(os.path.dirname(fstab))
            with open(fstab, 'w') as f:
                f.write('proc      /proc proc  defaults          0 0\n')
                f.write('sysfs     /sys  sysfs defaults          0 0\n')
                f.write('/dev/sda1 / btrfs defaults,rw,noatime 0 1\n')

    def _create_extlinux_config(self, path):
        self.app.status(msg='Creating extlinux.conf in %(path)s',
                        path=path, chatty=True)
        with self.build_watch('create-extlinux-config'):
            config = os.path.join(path, 'extlinux.conf')
            with open(config, 'w') as f:
                f.write('default linux\n')
                f.write('timeout 1\n')
                f.write('label linux\n')
                f.write('kernel /boot/vmlinuz\n')
                f.write('append root=/dev/sda1 rootflags=subvol=factory-run '
                        'init=/sbin/init rw\n')
    

class RootfsTarballBuilderPlugin(cliapp.Plugin):

    def enable(self):
        self.app.system_kind_builder_factory.register(RootfsTarballBuilder)
    
    def disable(self):
        pass

