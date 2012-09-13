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


def ldconfig(runcmd, rootdir):  # pragma: no cover
    '''Run ldconfig for the filesystem below ``rootdir``.

    Essentially, ``rootdir`` specifies the root of a new system.
    Only directories below it are considered.

    ``etc/ld.so.conf`` below ``rootdir`` is assumed to exist and
    be populated by the right directories, and should assume
    the root directory is ``rootdir``. Example: if ``rootdir``
    is ``/tmp/foo``, then ``/tmp/foo/etc/ld.so.conf`` should
    contain ``/lib``, not ``/tmp/foo/lib``.

    The ldconfig found via ``$PATH`` is used, not the one in ``rootdir``,
    since in bootstrap mode that might not yet exist, the various
    implementations should be compatible enough.

    '''

    conf = os.path.join(rootdir, 'etc', 'ld.so.conf')
    if os.path.exists(conf):
        logging.debug('Running ldconfig for %s' % rootdir)
        cache = os.path.join(rootdir, 'etc', 'ld.so.cache')

        # The following trickery with $PATH is necessary during the Baserock
        # bootstrap build: we are not guaranteed that PATH contains the
        # directory (/sbin conventionally) that ldconfig is in. Then again,
        # it might, and if so, we don't want to hardware a particular
        # location. So we add the possible locations to the end of $PATH
        env = dict(os.environ)
        old_path = env['PATH']
        env['PATH'] = '%s:/sbin:/usr/sbin:/usr/local/sbin' % old_path
        runcmd(['ldconfig', '-r', rootdir], env=env)
    else:
        logging.debug('No %s, not running ldconfig' % conf)


def download_depends(constituents, lac, rac, metadatas=None):
    for constituent in constituents:
        if not lac.has(constituent):
            source = rac.get(constituent)
            target = lac.put(constituent)
            shutil.copyfileobj(source, target)
            target.close()
            source.close()
        if metadatas is not None:
            for metadata in metadatas:
                if not lac.has_artifact_metadata(constituent, metadata):
                    if rac.has_artifact_metadata(constituent, metadata):
                        src = rac.get_artifact_metadata(constituent, metadata)
                        dst = lac.put_artifact_metadata(constituent, metadata)
                        shutil.copyfileobj(src, dst)
                        dst.close()
                        src.close()


def get_chunk_files(f):  # pragma: no cover
    tar = tarfile.open(fileobj=f)
    for member in tar.getmembers():
        if member.type is not tarfile.DIRTYPE:
            yield member.name
    tar.close()


def get_stratum_files(f, lac):  # pragma: no cover
    for ca in (ArtifactCacheReference(a) for a in json.load(f)):
        cf = lac.get(ca)
        for filename in get_chunk_files(cf):
            yield filename
        cf.close()


def get_overlaps(artifact, constituents, lac):  # pragma: no cover
    # check whether strata overlap
    installed = defaultdict(set)
    for dep in constituents:
        handle = lac.get(dep)
        if artifact.source.morphology['kind'] == 'stratum':
            for filename in get_chunk_files(handle):
                installed[filename].add(dep)
        elif artifact.source.morphology['kind'] == 'system':
            for filename in get_stratum_files(handle, lac):
                installed[filename].add(dep)
        handle.close()
    overlaps = defaultdict(set)
    for filename, artifacts in installed.iteritems():
        if len(artifacts) > 1:
            overlaps[frozenset(artifacts)].add(filename)
    return overlaps


def log_overlaps(overlaps):  # pragma: no cover
    for overlapping, files in sorted(overlaps.iteritems()):
        logging.warning('  Artifacts %s overlap with files:' %
                        ', '.join(sorted(a.name for a in overlapping)))
        for filename in sorted(files):
            logging.warning('    %s' % filename)


def write_overlap_metadata(artifact, overlaps, lac):  # pragma: no cover
    f = lac.put_artifact_metadata(artifact, 'overlaps')
    # the big list comprehension is because json can't serialize
    # artifacts, sets or dicts with non-string keys
    json.dump(
        [
            [
                [a.name for a in afs], list(files)
            ] for afs, files in overlaps.iteritems()
        ], f, indent=4)
    f.close()


class BuilderBase(object):

    '''Base class for building artifacts.'''

    def __init__(self, app, staging_area, local_artifact_cache,
                 remote_artifact_cache, artifact, repo_cache,
                 build_env, max_jobs, setup_mounts):
        self.app = app
        self.staging_area = staging_area
        self.local_artifact_cache = local_artifact_cache
        self.remote_artifact_cache = remote_artifact_cache
        self.artifact = artifact
        self.repo_cache = repo_cache
        self.build_env = build_env
        self.max_jobs = max_jobs
        self.build_watch = morphlib.stopwatch.Stopwatch()
        self.setup_mounts = setup_mounts

    def save_build_times(self):
        '''Write the times captured by the stopwatch'''
        meta = {
            'build-times': {}
        }
        for stage in self.build_watch.ticks.iterkeys():
            meta['build-times'][stage] = {
                'start': '%s' % self.build_watch.start_time(stage),
                'stop': '%s' % self.build_watch.stop_time(stage),
                'delta': '%.4f' % self.build_watch.start_stop_seconds(stage)
            }

        logging.debug('Writing metadata to the cache')
        with self.local_artifact_cache.put_source_metadata(
                self.artifact.source, self.artifact.cache_key,
                'meta') as f:
            json.dump(meta, f, indent=4, sort_keys=True)
            f.write('\n')

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
            'cache-key': self.artifact.cache_key,
            'cache-id': self.artifact.cache_id,
        }

        return meta

    # Wrapper around open() to allow it to be overridden by unit tests.
    def _open(self, filename, mode):  # pragma: no cover
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
        f.write(json.dumps(meta, indent=4, sort_keys=True))
        f.close()

    def new_artifact(self, artifact_name):
        '''Return an Artifact object for something built from our source.'''
        a = morphlib.artifact.Artifact(self.artifact.source, artifact_name)
        a.cache_key = self.artifact.cache_key
        return a

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

    def build_and_cache(self):  # pragma: no cover
        with self.build_watch('overall-build'):
            mounted = self.do_mounts()
            log_name = None
            try:
                builddir = self.staging_area.builddir(self.artifact.source)
                self.get_sources(builddir)
                destdir = self.staging_area.destdir(self.artifact.source)
                with self.local_artifact_cache.put_source_metadata(
                        self.artifact.source, self.artifact.cache_key,
                        'build-log') as log:
                    log_name = log.real_filename
                    self.run_commands(builddir, destdir, log)
            except:
                self.do_unmounts(mounted)
                if log_name:
                    with open(log_name) as f:
                        for line in f:
                            logging.error('OUTPUT FROM FAILED BUILD: %s' %
                                          line.rstrip('\n'))
                raise
            self.do_unmounts(mounted)
            built_artifacts = self.assemble_chunk_artifacts(destdir)

        self.save_build_times()
        return built_artifacts

    to_mount = (
        ('proc',    'proc',  'none'),
        ('dev/shm', 'tmpfs', 'none'),
    )

    def do_mounts(self):  # pragma: no cover
        mounted = []
        if not self.setup_mounts:
            return mounted
        for mount_point, mount_type, source in ChunkBuilder.to_mount:
            logging.debug('Mounting %s in staging area' % mount_point)
            path = os.path.join(self.staging_area.dirname, mount_point)
            if not os.path.exists(path):
                os.makedirs(path)
            self.app.runcmd(['mount', '-t', mount_type, source, path])
            mounted.append(path)
        return mounted

    def do_unmounts(self, mounted):  # pragma: no cover
        for path in mounted:
            logging.debug('Unmounting %s in staging area' % path)
            morphlib.fsutils.unmount(self.app.runcmd, path)

    def get_sources(self, srcdir):  # pragma: no cover
        '''Get sources from git to a source directory, for building.'''

        cache_dir = os.path.dirname(self.artifact.source.repo.path)

        def extract_repo(path, sha1, destdir):
            self.app.status(msg='Extracting %(source)s into %(target)s',
                            source=path,
                            target=destdir)
            if not os.path.exists(destdir):
                os.mkdir(destdir)
            morphlib.git.copy_repository(self.app.runcmd, path, destdir)
            morphlib.git.checkout_ref(self.app.runcmd, destdir, sha1)
            morphlib.git.reset_workdir(self.app.runcmd, destdir)
            submodules = morphlib.git.Submodules(self.app, path, sha1)
            try:
                submodules.load()
            except morphlib.git.NoModulesFileError:
                return []
            else:
                tuples = []
                for sub in submodules:
                    cached_repo = self.repo_cache.get_repo(sub.url)
                    sub_dir = os.path.join(destdir, sub.path)
                    tuples.append((cached_repo.path, sub.commit, sub_dir))
                return tuples

        s = self.artifact.source
        todo = [(s.repo.path, s.sha1, srcdir)]
        while todo:
            path, sha1, srcdir = todo.pop()
            todo += extract_repo(path, sha1, srcdir)
        self.set_mtime_recursively(srcdir)

    def set_mtime_recursively(self, root):  # pragma: no cover
        '''Set the mtime for every file in a directory tree to the same.

        We do this because git checkout does not set the mtime to anything,
        and some projects (binutils, gperf for example) include formatted
        documentation and try to randomly build things or not because of
        the timestamps. This should help us get more reliable  builds.

        '''

        now = time.time()
        for dirname, subdirs, basenames in os.walk(root.encode("utf-8"),
                                                   topdown=False):
            for basename in basenames:
                pathname = os.path.join(dirname, basename)
                # we need the following check to ignore broken symlinks
                if os.path.exists(pathname):
                    os.utime(pathname, (now, now))
            os.utime(dirname, (now, now))

    def run_commands(self, builddir, destdir, logfile):  # pragma: no cover
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
            with self.build_watch(step):
                key = '%s-commands' % step
                cmds = self.get_commands(key, m, bs)
                if cmds:
                    self.app.status(msg='Running %(key)s', key=key)
                    logfile.write('# %s\n' % step)
                for cmd in cmds:
                    if in_parallel:
                        max_jobs = self.artifact.source.morphology['max-jobs']
                        if max_jobs is None:
                            max_jobs = self.max_jobs
                        self.build_env.env['MAKEFLAGS'] = '-j%s' % max_jobs
                    else:
                        self.build_env.env['MAKEFLAGS'] = '-j1'
                    try:
                        # flushing is needed because writes from python and
                        # writes from being the output in Popen have different
                        # buffers, but flush handles both
                        logfile.write('# # %s\n' % cmd)
                        logfile.flush()
                        self.runcmd(['sh', '-c', cmd],
                                    cwd=relative_builddir,
                                    stdout=logfile,
                                    stderr=subprocess.STDOUT)
                        logfile.flush()
                    except cliapp.AppException, e:
                        logfile.flush()
                        with open(logfile.name, 'r') as readlog:
                            self.app.output.write("%s failed\n" % step)
                            shutil.copyfileobj(readlog, self.app.output)
                        raise e

    def assemble_chunk_artifacts(self, destdir):  # pragma: no cover
        built_artifacts = []
        with self.build_watch('create-chunks'):
            specs = self.artifact.source.morphology['chunks']
            if len(specs) == 0:
                specs = {
                    self.artifact.source.morphology['name']: ['.'],
                }
            names = specs.keys()
            names.sort(key=lambda name: [ord(c) for c in name])
            for artifact_name in names:
                self.write_metadata(destdir, artifact_name)
                patterns = specs[artifact_name]
                patterns += [r'baserock/%s\.' % artifact_name]

                artifact = self.new_artifact(artifact_name)
                with self.local_artifact_cache.put(artifact) as f:
                    logging.debug('assembling chunk %s' % artifact_name)
                    logging.debug('assembling into %s' % f.name)
                    self.app.status(msg='Creating chunk artifact %(name)s',
                                    name=artifact.name)
                    morphlib.bins.create_chunk(destdir, f, patterns)
                built_artifacts.append(artifact)

            files = os.listdir(destdir)
            if files:
                raise Exception('DESTDIR %s is not empty: %s' %
                                (destdir, files))
        return built_artifacts


class StratumBuilder(BuilderBase):

    '''Build stratum artifacts.'''

    def build_and_cache(self):  # pragma: no cover
        with self.build_watch('overall-build'):
            constituents = [dependency
                            for dependency in self.artifact.dependencies
                            if dependency.source.morphology['kind'] == 'chunk']
            if len(constituents) == 0:
                logging.warning('Stratum %s is empty' % self.artifact.name)
            # the only reason the StratumBuilder has to download chunks is to
            # check for overlap now that strata are lists of chunks
            with self.build_watch('check-chunks'):
                # download the chunk artifact if necessary
                download_depends(constituents,
                                 self.local_artifact_cache,
                                 self.remote_artifact_cache)
                # check for chunk overlaps
                overlaps = get_overlaps(self.artifact, constituents,
                                        self.local_artifact_cache)
                if len(overlaps) > 0:
                    logging.warning('Overlaps in stratum artifact %s detected'
                                    % self.artifact.name)
                    log_overlaps(overlaps)
                    self.app.status(msg='Overlaps in stratum artifact '
                                        '%(stratum_name)s detected',
                                    stratum_name=self.artifact.name,
                                    error=True)
                    write_overlap_metadata(self.artifact, overlaps,
                                           self.local_artifact_cache)

            with self.build_watch('create-chunk-list'):
                lac = self.local_artifact_cache
                artifact_name = self.artifact.source.morphology['name']
                artifact = self.new_artifact(artifact_name)
                meta = self.create_metadata(artifact_name)
                with lac.put_artifact_metadata(artifact, 'meta') as f:
                    json.dump(meta, f, indent=4, sort_keys=True)
                with self.local_artifact_cache.put(artifact) as f:
                    json.dump([c.basename() for c in constituents], f)
        self.save_build_times()
        return [artifact]


class SystemKindBuilder(BuilderBase):  # pragma: no cover

    '''Build a specific kind of a system.

    Subclasses should set the ``system_kind`` attribute to the kind of
    system they build.

    '''

    def unpack_strata(self, path):
        '''Unpack strata into a directory.'''

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

    def create_fstab(self, path):
        '''Create an /etc/fstab inside a system tree.

        The fstab is created using assumptions of the disk layout.
        If the assumptions are wrong, extend this code so it can deal
        with other cases.

        '''

        self.app.status(msg='Creating fstab in %(path)s',
                        path=path, chatty=True)
        with self.build_watch('create-fstab'):
            fstab = os.path.join(path, 'etc', 'fstab')
            # FIXME: should exist
            if not os.path.exists(os.path.dirname(fstab)):
                os.makedirs(os.path.dirname(fstab))
            with open(fstab, 'w') as f:
                f.write('proc      /proc proc  defaults          0 0\n')
                f.write('sysfs     /sys  sysfs defaults          0 0\n')
                f.write('/dev/sda1 / btrfs defaults,rw,noatime 0 1\n')

    def copy_kernel_into_artifact_cache(self, path):
        '''Copy the installed kernel image into the local artifact cache.

        The kernel image will be a separate artifact from the root
        filesystem/disk image/whatever. This is sometimes useful with
        funky bootloaders or virtualisation.

        '''

        name = self.artifact.source.morphology['name'] + '-kernel'
        a = self.new_artifact(name)
        with self.local_artifact_cache.put(a) as dest:
            for basename in ['zImage', 'vmlinuz']:
                installed_path = os.path.join(path, 'boot', basename)
                if os.path.exists(installed_path):
                    with open(installed_path) as kernel:
                        shutil.copyfileobj(kernel, dest)
                    break


class SystemKindBuilderFactory(object):  # pragma: no cover

    '''A factory class for SystemKindBuilder objects.'''

    def __init__(self):
        self.system_kinds = []

    def register(self, klass):
        self.system_kinds.append(klass)

    def new(self, system_kind, args, kwargs):
        for klass in self.system_kinds:
            if klass.system_kind == system_kind:
                return klass(*args, **kwargs)
        raise morphlib.Error("Don't know how to build system kind %s" %
                             system_kind)


class SystemBuilder(BuilderBase):  # pragma: no cover

    '''Build system image artifacts.'''

    def __init__(self, *args, **kwargs):
        BuilderBase.__init__(self, *args, **kwargs)
        self.args = args
        self.kwargs = kwargs

    def build_and_cache(self):
        system_kind = self.artifact.source.morphology['system-kind']
        builder = self.app.system_kind_builder_factory.new(
            system_kind, self.args, self.kwargs)
        logging.debug('Building system with %s' % repr(builder))
        self.app.status(msg='Building system %(system_name)s',
                        system_name=self.artifact.name)
        return builder.build_and_cache()


class Builder(object):  # pragma: no cover

    '''Helper class to build with the right BuilderBase subclass.'''

    classes = {
        'chunk': ChunkBuilder,
        'stratum': StratumBuilder,
        'system': SystemBuilder,
    }

    def __init__(self, app, staging_area, local_artifact_cache,
                 remote_artifact_cache, repo_cache, build_env, max_jobs,
                 setup_mounts):
        self.app = app
        self.staging_area = staging_area
        self.local_artifact_cache = local_artifact_cache
        self.remote_artifact_cache = remote_artifact_cache
        self.repo_cache = repo_cache
        self.build_env = build_env
        self.max_jobs = max_jobs
        self.setup_mounts = setup_mounts

    def build_and_cache(self, artifact):
        kind = artifact.source.morphology['kind']
        o = self.classes[kind](self.app, self.staging_area,
                               self.local_artifact_cache,
                               self.remote_artifact_cache, artifact,
                               self.repo_cache, self.build_env,
                               self.max_jobs, self.setup_mounts)
        logging.debug('Builder.build: artifact %s with %s' %
                      (artifact.name, repr(o)))
        built_artifacts = o.build_and_cache()
        logging.debug('Builder.build: done')
        return built_artifacts

class DiskImageBuilder(SystemKindBuilder):  # pragma: no cover

    system_kind = 'disk'

    def build_and_cache(self):
        with self.build_watch('overall-build'):
            arch = self.artifact.source.morphology['arch']

            rootfs_artifact = self.new_artifact(
                self.artifact.source.morphology['name'] + '-rootfs')
            handle = self.local_artifact_cache.put(rootfs_artifact)
            image_name = handle.name

            self._create_image(image_name)
            self._partition_image(image_name)
            self._install_mbr(arch, image_name)
            partition = self._setup_device_mapping(image_name)

            mount_point = None
            try:
                self._create_fs(partition)
                mount_point = self.staging_area.destdir(self.artifact.source)
                self._mount(partition, mount_point)
                factory_path = os.path.join(mount_point, 'factory')
                self._create_subvolume(factory_path)
                self.unpack_strata(factory_path)
                self.create_fstab(factory_path)
                self._create_bootloader_config(factory_path)
                self._create_subvolume_snapshot(
                    mount_point, 'factory', 'factory-run')
                factory_run_path = os.path.join(mount_point, 'factory-run')
                self._install_boot_files(arch, factory_run_path, mount_point)
                self._install_bootloader(mount_point)
                self.copy_kernel_into_artifact_cache(factory_path)
                self._unmount(mount_point)
            except BaseException, e:
                logging.error(traceback.format_exc())
                self.app.status(msg='Error while building system',
                                error=True)
                self._unmount(mount_point)
                self._undo_device_mapping(image_name)
                handle.abort()
                raise

            self._undo_device_mapping(image_name)
            handle.close()

        self.save_build_times()
        return [self.artifact]

    def _create_image(self, image_name):
        self.app.status(msg='Creating disk image %(filename)s',
                        filename=image_name, chatty=True)
        with self.build_watch('create-image'):
            morphlib.fsutils.create_image(
                self.app.runcmd, image_name,
                self.artifact.source.morphology['disk-size'])

    def _partition_image(self, image_name):
        self.app.status(msg='Partitioning disk image %(filename)s',
                        filename=image_name)
        with self.build_watch('partition-image'):
            morphlib.fsutils.partition_image(self.app.runcmd, image_name)

    def _install_mbr(self, arch, image_name):
        '''Placeholder method.'''

    def _setup_device_mapping(self, image_name):
        self.app.status(msg='Device mapping partitions in %(filename)s',
                        filename=image_name, chatty=True)
        with self.build_watch('setup-device-mapper'):
            return morphlib.fsutils.setup_device_mapping(self.app.runcmd,
                                                         image_name)

    def _create_fs(self, partition):
        self.app.status(msg='Creating filesystem on %(partition)s',
                        partition=partition, chatty=True)
        with self.build_watch('create-filesystem'):
            morphlib.fsutils.create_fs(self.app.runcmd, partition)

    def _mount(self, partition, mount_point):
        self.app.status(msg='Mounting %(partition)s on %(mount_point)s',
                        partition=partition, mount_point=mount_point,
                        chatty=True)
        with self.build_watch('mount-filesystem'):
            morphlib.fsutils.mount(self.app.runcmd, partition, mount_point)

    def _create_subvolume(self, path):
        self.app.status(msg='Creating subvolume %(path)s',
                        path=path, chatty=True)
        with self.build_watch('create-factory-subvolume'):
            self.app.runcmd(['btrfs', 'subvolume', 'create', path])

    def _create_bootloader_config(self, path):
        '''Placeholder method.'''

    def _create_subvolume_snapshot(self, path, source, target):
        self.app.status(msg='Creating subvolume snapshot '
                            '%(source)s to %(target)s',
                        source=source, target=target, chatty=True)
        with self.build_watch('create-runtime-snapshot'):
            # sync needed for older versions of btrfs where files aren't
            # flushed to disk before they have their contents snapshotted
            self.app.runcmd(['sync'])
            self.app.runcmd(['btrfs', 'subvolume', 'snapshot', source, target],
                            cwd=path)

    def _install_boot_files(self, arch, sourcefs, targetfs):
        with self.build_watch('install-boot-files'):
            if arch in ('x86', 'x86_64'):
                self.app.status(msg='Installing boot files into root volume',
                                chatty=True)
                os.mkdir(os.path.join(targetfs, 'boot'))
                shutil.copy2(os.path.join(sourcefs, 'boot', 'vmlinuz'),
                             os.path.join(targetfs, 'boot', 'vmlinuz'))
                shutil.copy2(os.path.join(sourcefs, 'boot', 'System.map'),
                             os.path.join(targetfs, 'boot', 'System.map'))

    def _install_bootloader(self, path):
        '''Placeholder method.'''

    def _unmount(self, mount_point):
        with self.build_watch('unmount-filesystem'):
            if mount_point is not None:
                self.app.status(msg='Unmounting %(mount_point)s',
                                mount_point=mount_point, chatty=True)
                morphlib.fsutils.unmount(self.app.runcmd, mount_point)

    def _undo_device_mapping(self, image_name):
        self.app.status(msg='Undoing device mappings for %(filename)s',
                        filename=image_name, chatty=True)
        with self.build_watch('undo-device-mapper'):
            morphlib.fsutils.undo_device_mapping(self.app.runcmd, image_name)


