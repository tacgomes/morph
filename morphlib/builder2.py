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
import time

import morphlib


class BuilderBase(object):

    '''Base class for building artifacts.'''

    def __init__(self, staging_area, artifact_cache, artifact, build_env, 
                 max_jobs):
        self.staging_area = staging_area
        self.artifact_cache = artifact_cache
        self.artifact = artifact
        self.build_env = build_env
        self.max_jobs = max_jobs
    
    def create_metadata(self, artifact_name):
        '''Create metadata to artifact to allow it to be reproduced later.
        
        The metadata is represented as a dict, which later on will be
        written out as a JSON file.
        
        '''
        
        assert isinstance(self.artifact.source.repo, 
                          morphlib.cachedrepo.CachedRepo)
        meta = {
            'artifact-name': artifact_name,
            'source-name': self.artifact.source.morphology['name'],
            'kind': self.artifact.source.morphology['kind'],
            'description': self.artifact.source.morphology['description'],
            'repo': self.artifact.source.repo.url,
            'original_ref': self.artifact.source.original_ref,
            'sha1': self.artifact.source.sha1,
            'morphology': self.artifact.source.filename,
        }
        
        return meta

    # Wrapper around open() to allow it to be overridden by unit tests.
    def _open(self, filename, mode): # pragma: no cover
        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        return open(filename, mode)

    def write_metadata(self, instdir, artifact_name):
        '''Write the metadata for an artifact.
        
        The file will be located under the ``baserock`` directory under
        instdir, named after ``cache_key`` with ``.meta`` as the suffix.
        It will be in JSON format.
        
        '''
        
        meta = self.create_metadata(artifact_name)

        basename = '%s.meta' % artifact_name
        filename = os.path.join(instdir, 'baserock', basename)

        # Unit tests use StringIO, which in Python 2.6 isn't usable with
        # the "with" statement. So we don't do it with "with".
        f = self._open(filename, 'w')
        f.write(json.dumps(meta))
        f.close()
        
    def new_artifact(self, artifact_name):
        '''Return an Artifact object for something built from our source.'''
        return morphlib.artifact.Artifact(self.artifact.source, artifact_name)
        
    def runcmd(self, *args, **kwargs):
        kwargs['env'] = self.build_env.env
        return self.staging_area.runcmd(*args, **kwargs)


class ChunkBuilder(BuilderBase):

    '''Build chunk artifacts.'''
    
    def get_commands(self, which, morphology, build_system):
        '''Return the commands to run from a morphology or the build system.'''
        if morphology[which] is None:
            attr = '_'.join(which.split('-'))
            return getattr(build_system, attr)
        else:
            return morphology[which]

    def build_and_cache(self): # pragma: no cover
        builddir = self.staging_area.builddir(self.artifact.source)
        self.get_sources(builddir)
        destdir = self.staging_area.destdir(self.artifact.source)
        self.run_commands(builddir, destdir)
        self.assemble_chunk_artifacts(destdir)

    def get_sources(self, srcdir): # pragma: no cover
        '''Get sources from git to a source directory, for building.'''

        def extract_repo(path, sha1, destdir):
            logging.debug('Extracting %s into %s' % (path, destdir))
            if not os.path.exists(destdir):
                os.mkdir(destdir)
            morphlib.git.copy_repository(path, destdir, logging.debug)
            morphlib.git.checkout_ref(destdir, sha1, logging.debug)
            morphlib.git.reset_workdir(destdir, logging.debug)
            submodules = morphlib.git.Submodules(path, sha1)
            try:
                submodules.load()
            except morphlib.git.NoModulesFileError:
                return []
            else:
                return [(sub.path, sub.commit, os.path.join(destdir, sub.path))
                        for sub in submodules]

        s = self.artifact.source
        todo = [(s.repo.path, s.sha1, srcdir)]
        while todo:
            path, sha1, srcdir = todo.pop()
            todo += extract_repo(path, sha1, srcdir)
        self.set_mtime_recursively(srcdir)

    def set_mtime_recursively(self, root): # pragma: no cover
        '''Set the mtime for every file in a directory tree to the same.
        
        We do this because git checkout does not set the mtime to anything,
        and some projects (binutils, gperf for example) include formatted
        documentation and try to randomly build things or not because of
        the timestamps. This should help us get more reliable  builds.
        
        '''
        
        now = time.time()
        for dirname, subdirs, basenames in os.walk(root, topdown=False):
            for basename in basenames:
                pathname = os.path.join(dirname, basename)
                # we need the following check to ignore broken symlinks
                if os.path.exists(pathname):
                    os.utime(pathname, (now, now))
            os.utime(dirname, (now, now))


    def run_commands(self, builddir, destdir): # pragma: no cover
        m = self.artifact.source.morphology
        bs = morphlib.buildsystem.lookup_build_system(m['build-system'])

        relative_builddir = self.staging_area.relative(builddir)
        relative_destdir = self.staging_area.relative(destdir)
        self.build_env.env['DESTDIR'] = relative_destdir

        steps = [('configure', False), 
                 ('build', True),
                 ('test', False),
                 ('install', False)]
        for step, in_parallel in steps:
            cmds = self.get_commands('%s-commands' % step, m, bs)
            for cmd in cmds:
                if in_parallel:
                    max_jobs = self.artifact.source.morphology['max-jobs']
                    if max_jobs is None:
                        max_jobs = self.max_jobs
                    self.build_env.env['MAKEFLAGS'] = '-j%s' % max_jobs
                else:
                    self.build_env.env['MAKEFLAGS'] = '-j1'
                self.runcmd(['sh', '-c', cmd], cwd=relative_builddir)

    def assemble_chunk_artifacts(self, destdir): # pragma: no cover
        ex = None # create_chunk doesn't actually use this
        specs = self.artifact.source.morphology['chunks']
        if len(specs) == 0:
            specs = {
                self.artifact.source.morphology['name']: ['.'],
            }
        for artifact_name in specs:
            self.write_metadata(destdir, artifact_name)
            patterns = specs[artifact_name]
            patterns += [r'baserock/%s\.' % artifact_name]

            artifact = self.new_artifact(artifact_name)
            with self.artifact_cache.put(artifact) as f:
                logging.debug('assembling chunk %s' % artifact_name)
                logging.debug('assembling into %s' % f.name)
                morphlib.bins.create_chunk(destdir, f, patterns, ex)

        files = os.listdir(destdir)
        if files:
            raise Exception('DESTDIR %s is not empty: %s' % (destdir, files))


class StratumBuilder(BuilderBase):

    '''Build stratum artifacts.'''

    def build_and_cache(self): # pragma: no cover
        destdir = self.staging_area.destdir(self.artifact.source)

        constituents = [dependency
                        for dependency in self.artifact.dependencies
                        if dependency.source.morphology['kind'] == 'chunk']
        for chunk_artifact in constituents:
            with self.artifact_cache.get(chunk_artifact) as f:
                morphlib.bins.unpack_binary_from_file(f, destdir)

        artifact_name = self.artifact.source.morphology['name']
        self.write_metadata(destdir, artifact_name)
        artifact = self.new_artifact(artifact_name)
        with self.artifact_cache.put(artifact) as f:
            morphlib.bins.create_stratum(destdir, f, None)


class SystemBuilder(BuilderBase): # pragma: no cover

    '''Build system image artifacts.'''

    def build_and_cache(self):
        logging.debug('SystemBuilder.do_build called')
        self.ex = morphlib.execute.Execute(self.staging_area.dirname,
                                           logging.debug)
        
        image_name = os.path.join(self.staging_area.dirname,
                                  '%s.img' % self.artifact.name)
        self._create_image(image_name)
        self._partition_image(image_name)
        self._install_mbr(image_name)
        partition = self._setup_device_mapping(image_name)

        mount_point = None
        try:
            self._create_fs(partition)
            mount_point = self.staging_area.destdir(self.artifact.source)
            self._mount(partition, mount_point)
            factory_path = os.path.join(mount_point, 'factory')
            self._create_subvolume(factory_path)
            self._unpack_strata(factory_path)
            self._create_fstab(factory_path)
            self._create_extlinux_config(factory_path)
            self._create_subvolume_snapshot(
                    mount_point, 'factory', 'factory-run')
            factory_run_path = os.path.join(mount_point, 'factory-run')
            self._install_boot_files(factory_run_path, mount_point)
            self._install_extlinux(mount_point)
            self._unmount(mount_point)
        except BaseException:
            self._unmount(mount_point)
            self._undo_device_mapping(image_name)
            raise

        self._undo_device_mapping(image_name)
        self._move_image_to_cache(image_name)

    def _create_image(self, image_name):
        morphlib.fsutils.create_image(self.ex, image_name,
                                      self.artifact.morphology['disk-size'])

    def _partition_image(self, image_name):
        morphlib.fsutils.partition_image(self.ex, image_name)

    def _install_mbr(self, image_name):
        morphlib.fsutils.install_mbr(self.ex, image_name)

    def _setup_device_mapping(self, image_name):
        return morphlib.fsutils.setup_device_mapping(self.ex, image_name)

    def _create_fs(self, partition):
        morphlib.fsutils.create_fs(self.ex, partition)

    def _mount(self, partition, mount_point):
        morphlib.fsutils.mount(self.ex, partition, mount_point)

    def _create_subvolume(self, path):
        self.ex.runv(['btrfs', 'subvolume', 'create', path])

    def _unpack_strata(self, path):
        for stratum_artifact in self.artifact.dependencies:
            with self.artifact_cache.get(stratum_artifact) as f:
                morphlib.bins.unpack_binary_from_file(f, path, self.ex)
        morphlib.builder.ldconfig(self.ex, path)

    def _create_fstab(self, path):
        fstab = os.path.join(path, 'etc', 'fstab')
        if not os.path.exists(os.path.dirname(fstab)): # FIXME: should exist
            os.makedirs(os.path.dirname(fstab))
        with open(fstab, 'w') as f:
            f.write('proc      /proc proc  defaults          0 0\n')
            f.write('sysfs     /sys  sysfs defaults          0 0\n')
            f.write('/dev/sda1 / btrfs errors=remount-ro 0 1\n')

    def _create_extlinux_config(self, path):
        config = os.path.join(path, 'extlinux.conf')
        with open(config, 'w') as f:
            f.write('default linux\n')
            f.write('timeout 1\n')
            f.write('label linux\n')
            f.write('kernel /boot/vmlinuz\n')
            f.write('append root=/dev/sda1 rootflags=subvol=factory-run '
                                           'init=/sbin/init quiet rw\n')

    def _create_subvolume_snapshot(self, path, source, target):
        self.ex.runv(['btrfs', 'subvolume', 'snapshot', source, target],
                     cwd=path)

    def _install_boot_files(self, sourcefs, targetfs):
        logging.debug('installing boot files into root volume')
        shutil.copy2(os.path.join(sourcefs, 'extlinux.conf'),
                     os.path.join(targetfs, 'extlinux.conf'))
        os.mkdir(os.path.join(targetfs, 'boot'))
        shutil.copy2(os.path.join(sourcefs, 'boot', 'vmlinuz'),
                     os.path.join(targetfs, 'boot', 'vmlinuz'))
        shutil.copy2(os.path.join(sourcefs, 'boot', 'System.map'),
                     os.path.join(targetfs, 'boot', 'System.map'))

    def _install_extlinux(self, path):
        self.ex.runv(['extlinux', '--install', path])

        # FIXME this hack seems to be necessary to let extlinux finish
        self.ex.runv(['sync'])
        time.sleep(2)

    def _unmount(self, mount_point):
        if mount_point is not None:
            morphlib.fsutils.unmount(self.ex, mount_point)

    def _undo_device_mapping(self, image_name):
        morphlib.fsutils.undo_device_mapping(self.ex, image_name)

    def _move_image_to_cache(self, image_name):
        # FIXME: Need to create file directly in cache to avoid costly
        # copying here.
        with self.artifact_cache.put(self.artifact) as outf:
            with open(image_name) as inf:
                while True:
                    data = inf.read(1024**2)
                    if not data:
                        break
                    outf.write(data)


class Builder(object): # pragma: no cover

    '''Helper class to build with the right BuilderBase subclass.'''
    
    classes = {
        'chunk': ChunkBuilder,
        'stratum': StratumBuilder,
        'system': SystemBuilder,
    }

    def __init__(self, staging_area, artifact_cache, build_env, max_jobs):
        self.staging_area = staging_area
        self.artifact_cache = artifact_cache
        self.build_env = build_env
        self.max_jobs = max_jobs
        
    def build_and_cache(self, artifact):
        kind = artifact.source.morphology['kind']
        o = self.classes[kind](self.staging_area, self.artifact_cache, 
                               artifact, self.build_env, self.max_jobs)
        logging.debug('Builder.build: artifact %s with %s' %
                      (artifact.name, repr(o)))
        o.build_and_cache()
        logging.debug('Builder.build: done')

