# Copyright (C) 2011  Codethink Limited
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
import StringIO
import tarfile
import urlparse

import morphlib


class BinaryBlob(object):

    def __init__(self, morph, repo, ref):
        self.morph = morph
        self.repo = repo
        self.ref = ref
        
        # The following MUST get set by the caller.
        self.builddir = None
        self.destdir = None
        self.staging = None
        self.settings = None
        self.msg = None
        self.cache_prefix = None
        self.tempdir = None
        self.built = None
        self.dump_memory_profile = lambda msg: None

        # Stopwatch to measure build times
        self.build_watch = morphlib.stopwatch.Stopwatch()

    def dict_key(self):
        return {}
    
    def needs_built(self):
        return []

    def builds(self):
        raise NotImplemented()
    
    def build(self):
        raise NotImplemented()

    def filename(self, name):
        return '%s.%s.%s' % (self.cache_prefix, self.morph.kind, name)

    def prepare_binary_metadata(self, blob_name, **kwargs):
        '''Add metadata to a binary about to be built.'''

        self.msg('Adding metadata to %s' % blob_name)
        meta = {
            'name': blob_name,
            'kind': self.morph.kind,
            'description': self.morph.description,
        }
        for key, value in kwargs.iteritems():
            meta[key] = value
        
        dirname = os.path.join(self.destdir, 'baserock')
        filename = os.path.join(dirname, '%s.meta' % blob_name)
        if not os.path.exists(dirname):
            os.mkdir(dirname)
        with open(filename, 'w') as f:
            json.dump(meta, f, indent=4)
            f.write('\n')

    def write_cache_metadata(self, meta):
        self.msg('Writing metadata to the cache')
        filename = '%s.meta' % self.cache_prefix
        with open(filename, 'w') as f:
            json.dump(meta, f, indent=4)
            f.write('\n')

    def save_build_times(self):
        meta = {
            'build-times': {}
        }
        for stage in self.build_watch.ticks.iterkeys():
            delta = self.build_watch.start_stop_delta(stage)
            meta['build-times'][stage] = {
                'start': '%s' % self.build_watch.start_time(stage),
                'stop': '%s' % self.build_watch.stop_time(stage),
                'delta': delta.total_seconds()
            }
        self.write_cache_metadata(meta)


class Chunk(BinaryBlob):

    build_system = {
        'autotools': {
            'configure-commands': [
                'if [ -e autogen.sh ]; then ./autogen.sh; fi',
                './configure --prefix=/usr',
            ],
            'build-commands': [
                'make',
            ],
            'test-commands': [
            ],
            'install-commands': [
                'make DESTDIR="$DESTDIR" install',
            ],
        },
    }

    @property
    def chunks(self):
        if self.morph.chunks:
            return self.morph.chunks
        else:
            return { self.morph.name: ['.'] }
    
    def builds(self):
        ret = {}
        for chunk_name in self.chunks:
            ret[chunk_name] = self.filename(chunk_name)
        return ret

    def build(self):
        logging.debug('Creating build tree at %s' % self.builddir)

        self.ex = morphlib.execute.Execute(self.builddir, self.msg)
        self.setup_env()

        self.create_source_and_tarball()

        os.mkdir(self.destdir)
        if self.morph.build_system:
            self.build_using_buildsystem()
        else:
            self.build_using_commands()
        self.dump_memory_profile('after building chunk')

        chunks = self.create_chunks(self.chunks)
        self.dump_memory_profile('after creating chunk blobs')
        return chunks
        
    def setup_env(self):
        path = self.ex.env['PATH']
        tools = self.ex.env.get('BOOTSTRAP_TOOLS')
        distcc_hosts = self.ex.env.get('DISTCC_HOSTS')
        self.ex.env.clear()
        
        self.ex.env['TERM'] = 'dumb'
        self.ex.env['SHELL'] = '/bin/sh'
        self.ex.env['USER'] = \
            self.ex.env['USERNAME'] = \
            self.ex.env['LOGNAME'] = 'tomjon'
        self.ex.env['LC_ALL'] = 'C'
        self.ex.env['HOME'] = os.path.join(self.tempdir.dirname)

        if self.settings['keep-path'] or self.settings['bootstrap']:
            self.ex.env['PATH'] = path
        else:
            bindirs = ['bin']
            path = ':'.join(os.path.join(self.tempdir.dirname, x) 
                                         for x in bindirs)
            self.ex.env['PATH'] = path

        self.ex.env['WORKAREA'] = self.tempdir.dirname
        self.ex.env['DESTDIR'] = self.destdir + '/'
        self.ex.env['TOOLCHAIN_TARGET'] = \
            '%s-baserock-linux-gnu' % os.uname()[4]
        self.ex.env['BOOTSTRAP'] = \
            'true' if self.settings['bootstrap'] else 'false'
        if tools is not None:
            self.ex.env['BOOTSTRAP_TOOLS'] = tools
        if distcc_hosts is not None:
            self.ex.env['DISTCC_HOSTS'] = distcc_hosts

        if self.morph.max_jobs:
            max_jobs = int(self.morph.max_jobs)
            logging.debug('max_jobs from morph: %s' % max_jobs)
        elif self.settings['max-jobs']:
            max_jobs = self.settings['max-jobs']
            logging.debug('max_jobs from settings: %s' % max_jobs)
        else:
            max_jobs = morphlib.util.make_concurrency()
            logging.debug('max_jobs from cpu count: %s' % max_jobs)
        self.ex.env['MAKEFLAGS'] = '-j%d' % max_jobs

        if not self.settings['no-ccache']:
            self.ex.env['PATH'] = ('/usr/lib/ccache:%s' % 
                                    self.ex.env['PATH'])
            self.ex.env['CCACHE_BASEDIR'] = self.tempdir.dirname
            if not self.settings['no-distcc']:
                self.ex.env['CCACHE_PREFIX'] = 'distcc'

        logging.debug('Environment for building chunk:')
        for key in sorted(self.ex.env):
            logging.debug('  %s=%s' % (key, self.ex.env[key]))

    def create_source_and_tarball(self):
        self.msg('Creating source tree and tarball')
        self.build_watch.start('create-source-tarball')
        self.dump_memory_profile('before creating source and tarball for chunk')
        tarball = self.cache_prefix + '.src.tar'
        morphlib.git.export_sources(self.repo, self.ref, tarball)
        self.dump_memory_profile('after exporting sources')
        os.mkdir(self.builddir)
        self.ex.runv(['tar', '-C', self.builddir, '-xf', tarball])
        self.dump_memory_profile('after creating source and tarball for chunk')
        self.build_watch.stop('create-source-tarball')

    def build_using_buildsystem(self):
        bs_name = self.morph.build_system
        self.msg('Building using well-known build system %s' % bs_name)
        bs = self.build_system[bs_name]
        self.run_sequentially('configure', bs['configure-commands'])
        self.run_in_parallel('build', bs['build-commands'])
        self.run_sequentially('test', bs['test-commands'])
        self.run_sequentially('install', bs['install-commands'],
                              as_fakeroot=True)

    def build_using_commands(self):
        self.msg('Building using explicit commands')
        self.run_sequentially('configure', self.morph.configure_commands)
        self.run_in_parallel('build', self.morph.build_commands)
        self.run_sequentially('test', self.morph.test_commands)
        self.run_sequentially('install', self.morph.install_commands,
                              as_fakeroot=True)

    def run_in_parallel(self, what, commands):
        self.msg('commands: %s' % what)
        self.build_watch.start(what)
        self.ex.run(commands)
        self.build_watch.stop(what)

    def run_sequentially(self, what, commands, as_fakeroot=False):
        self.msg ('commands: %s' % what)
        self.build_watch.start(what)
        flags = self.ex.env['MAKEFLAGS']
        self.ex.env['MAKEFLAGS'] = '-j1'
        logging.debug('Setting MAKEFLAGS=%s' % self.ex.env['MAKEFLAGS'])
        self.ex.run(commands, as_fakeroot=as_fakeroot)
        self.ex.env['MAKEFLAGS'] = flags
        logging.debug('Restore MAKEFLAGS=%s' % self.ex.env['MAKEFLAGS'])
        self.build_watch.stop(what)

    def create_chunks(self, chunks):
        ret = {}
        self.build_watch.start('create-chunks')
        for chunk_name in chunks:
            self.msg('Creating chunk %s' % chunk_name)
            self.prepare_binary_metadata(chunk_name)
            patterns = chunks[chunk_name]
            patterns += [r'baserock/%s\.' % chunk_name]
            filename = self.filename(chunk_name)
            self.msg('Creating binary for %s' % chunk_name)
            morphlib.bins.create_chunk(self.destdir, filename, patterns,
                                       self.dump_memory_profile)
            ret[chunk_name] = filename
        self.build_watch.stop('create-chunks')
        files = os.listdir(self.destdir)
        if files:
            raise Exception('DESTDIR %s is not empty: %s' %
                                (self.destdir, files))
        return ret


class Stratum(BinaryBlob):
    
    def needs_built(self):
        for source in self.morph.sources:
            project_name = source['name']
            morph_name = source['morph'] if 'morph' in source else project_name
            repo = source['repo']
            ref = source['ref']
            chunks = source['chunks'] if 'chunks' in source else [project_name]
            yield repo, ref, morph_name, chunks

    def builds(self):
        filename = self.filename(self.morph.name)
        return { self.morph.name: filename }

    def build(self):
        os.mkdir(self.destdir)
        self.build_watch.start('unpack-chunks')
        for chunk_name, filename in self.built:
            self.msg('Unpacking chunk %s' % chunk_name)
            morphlib.bins.unpack_binary(filename, self.destdir)
        self.build_watch.stop('unpack-chunks')
        self.prepare_binary_metadata(self.morph.name)
        self.build_watch.start('create-binary')
        self.msg('Creating binary for %s' % self.morph.name)
        filename = self.filename(self.morph.name)
        morphlib.bins.create_stratum(self.destdir, filename)
        self.build_watch.stop('create-binary')
        return { self.morph.name: filename }


class System(BinaryBlob):

    def needs_built(self):
        for stratum_name in self.morph.strata:
            yield self.repo, self.ref, stratum_name, [stratum_name]

    def builds(self):
        filename = self.filename(self.morph.name)
        return { self.morph.name: filename }

    def build(self):
        self.ex = morphlib.execute.Execute(self.tempdir.dirname, self.msg)
        
        # Create image.
        self.build_watch.start('create-image')
        image_name = self.tempdir.join('%s.img' % self.morph.name)
        self.ex.runv(['qemu-img', 'create', '-f', 'raw', image_name,
                      self.morph.disk_size])
        self.build_watch.stop('create-image')

        # Partition it.
        self.build_watch.start('partition-image')
        self.ex.runv(['parted', '-s', image_name, 'mklabel', 'msdos'],
                     as_root=True)
        self.ex.runv(['parted', '-s', image_name, 'mkpart', 'primary', 
                      '0%', '100%'], as_root=True)
        self.ex.runv(['parted', '-s', image_name, 'set', '1', 'boot', 'on'],
                     as_root=True)
        self.build_watch.stop('partition-image')

        # Install first stage boot loader into MBR.
        self.build_watch.start('install-mbr')
        self.ex.runv(['install-mbr', image_name], as_root=True)
        self.build_watch.stop('install-mbr')

        # Setup device mapper to access the partition.
        self.build_watch.start('setup-device-mapper')
        out = self.ex.runv(['kpartx', '-av', image_name], as_root=True)
        devices = [line.split()[2]
                   for line in out.splitlines()
                   if line.startswith('add map ')]
        partition = '/dev/mapper/%s' % devices[0]
        self.build_watch.stop('setup-device-mapper')

        mount_point = None
        try:
            # Create filesystem.
            self.build_watch.start('create-filesystem')
            self.ex.runv(['mkfs', '-t', 'ext3', partition], as_root=True)
            self.build_watch.stop('create-filesystem')
            
            # Mount it.
            self.build_watch.start('mount-filesystem')
            mount_point = self.tempdir.join('mnt')
            os.mkdir(mount_point)
            self.ex.runv(['mount', partition, mount_point], as_root=True)
            self.build_watch.stop('mount-filesystem')

            # Unpack all strata into filesystem.
            self.build_watch.start('unpack-strata')
            for name, filename in self.built:
                self.msg('unpack %s from %s' % (name, filename))
                self.ex.runv(['tar', '-C', mount_point, '-xf', filename],
                             as_root=True)
            self.build_watch.stop('unpack-strata')

            # Create fstab.
            self.build_watch.start('create-fstab')
            fstab = self.tempdir.join('mnt/etc/fstab')
            with open(fstab, 'w') as f:
                f.write('proc /proc proc defaults 0 0\n')
                f.write('sysfs /sys sysfs defaults 0 0\n')
                f.write('/dev/sda1 / ext4 errors=remount-ro 0 1\n')
            self.build_watch.stop('create-fstab')

            # Install extlinux bootloader.
            self.build_watch.start('install-bootloader')
            conf = os.path.join(mount_point, 'extlinux.conf')
            logging.debug('configure extlinux %s' % conf)
            f = open(conf, 'w')
            f.write('''
default linux
timeout 1

label linux
kernel /vmlinuz
append root=/dev/sda1 init=/bin/sh quiet rw
''')
            f.close()

            self.ex.runv(['extlinux', '--install', mount_point], as_root=True)
            
            # Weird hack that makes extlinux work. There is a bug somewhere.
            self.ex.runv(['sync'])
            import time; time.sleep(2)
            self.build_watch.stop('install-bootloader')

            # Unmount.
            self.build_watch.start('unmount-filesystem')
            self.ex.runv(['umount', mount_point], as_root=True)
            self.build_watch.stop('unmount-filesystem')
        except BaseException, e:
            # Unmount.
            if mount_point is not None:
                try:
                    self.ex.runv(['umount', mount_point], as_root=True)
                except Exception:
                    pass

            # Undo device mapping.
            try:
                self.ex.runv(['kpartx', '-d', image_name], as_root=True)
            except Exception:
                pass
            raise

        # Undo device mapping.
        self.build_watch.start('undo-device-mapper')
        self.ex.runv(['kpartx', '-d', image_name], as_root=True)
        self.build_watch.stop('undo-device-mapper')

        # Move image file to cache.
        self.build_watch.start('cache-image')
        filename = self.filename(self.morph.name)
        self.ex.runv(['mv', image_name, filename])
        self.build_watch.stop('cache-image')

        return { self.morph.name: filename }

class Builder(object):

    '''Build binary objects for Baserock.
    
    The objects may be chunks or strata.'''
    
    def __init__(self, tempdir, app):
        self.tempdir = tempdir
        self.real_msg = app.msg
        self.settings = app.settings
        self.dump_memory_profile = app.dump_memory_profile
        self.cachedir = morphlib.cachedir.CacheDir(self.settings['cachedir'])
        self.indent = 0

    def msg(self, text):
        spaces = '  ' * self.indent
        self.real_msg('%s%s' % (spaces, text))

    def indent_more(self):
        self.indent += 1
    
    def indent_less(self):
        self.indent -= 1

    def build(self, repo, ref, filename):
        '''Build a binary based on a morphology.'''

        self.dump_memory_profile('at start of build method')
        self.indent_more()
        self.msg('build %s|%s|%s' % (repo, ref, filename))
        base_url = self.settings['git-base-url']
        if not base_url.endswith('/'):
            base_url += '/'
        repo = urlparse.urljoin(base_url, repo)
        morph = self.get_morph_from_git(repo, ref, filename)
        self.dump_memory_profile('after getting morph from git')

        if morph.kind == 'chunk':
            blob = Chunk(morph, repo, ref)
        elif morph.kind == 'stratum':
            blob = Stratum(morph, repo, ref)
        elif morph.kind == 'system':
            blob = System(morph, repo, ref)
        else:
            raise Exception('Unknown kind of morphology: %s' % morph.kind)
        self.dump_memory_profile('after creating Chunk/Stratum/...')

        dict_key = blob.dict_key()
        self.complete_dict_key(dict_key, morph.name, repo, ref)
        logging.debug('completed dict_key:\n%s' % repr(dict_key))
        self.dump_memory_profile('after completing cache key')

        blob.builddir = self.tempdir.join('%s.build' % morph.name)
        blob.destdir = self.tempdir.join('%s.inst' % morph.name)
        blob.staging = self.tempdir.join('staging')
        if not os.path.exists(blob.staging):
            os.mkdir(blob.staging)
        blob.settings = self.settings
        blob.msg = self.msg
        blob.cache_prefix = self.cachedir.name(dict_key)
        blob.tempdir = self.tempdir
        blob.dump_memory_profile = self.dump_memory_profile

        builds = blob.builds()
        self.dump_memory_profile('after blob.builds()')
        if all(os.path.exists(builds[x]) for x in builds):
            for x in builds:
                self.msg('using cached %s %s at %s' % 
                            (morph.kind, x, builds[x]))
                self.install_chunk(morph, x, builds[x], blob.staging)
                self.dump_memory_profile('after installing chunk')
            built = builds
        else:
            blob.build_watch.start('overall-build')

            blob.build_watch.start('build-needed')
            self.build_needed(blob)
            blob.build_watch.stop('build-needed')
            self.dump_memory_profile('after building needed')

            self.msg('Building %s %s' % (morph.kind, morph.name))
            self.indent_more()
            built = blob.build()
            self.dump_memory_profile('after building blob')
            self.indent_less()
            for x in built:
                self.msg('%s %s cached at %s' % (morph.kind, x, built[x]))
                self.install_chunk(morph, x, built[x], blob.staging)
                self.dump_memory_profile('after installing chunks')

            blob.build_watch.stop('overall-build')
            blob.save_build_times()

        self.indent_less()
        self.dump_memory_profile('at end of build method')
        return built

    def build_needed(self, blob):
        blob.built = []
        for repo, ref, morph_name, blob_names in blob.needs_built():
            morph_filename = '%s.morph' % morph_name
            cached = self.build(repo, ref, morph_filename)
            for blob_name in blob_names:
                blob.built.append((blob_name, cached[blob_name]))

    def install_chunk(self, morph, chunk_name, chunk_filename, staging_dir):
        if morph.kind != 'chunk':
            return
        if self.settings['bootstrap']:
            self.msg('Unpacking chunk %s onto system' % chunk_name)
            morphlib.bins.unpack_binary(chunk_filename, '/')
        else:
            self.msg('Unpacking chunk %s into staging' % chunk_name)
            morphlib.bins.unpack_binary(chunk_filename, staging_dir)
            
    def complete_dict_key(self, dict_key, name, repo, ref):
        '''Fill in default fields of a cache's dict key.'''

        if repo and ref:
            abs_ref = morphlib.git.get_commit_id(repo, ref)
        else:
            abs_ref = ''

        dict_key['name'] = name
        dict_key['arch'] = morphlib.util.arch()
        dict_key['repo'] = repo
        dict_key['ref'] = abs_ref

    def get_morph_from_git(self, repo, ref, filename):
        morph_text = morphlib.git.get_morph_text(repo, ref, filename)
        f = StringIO.StringIO(morph_text)
        f.name = filename
        morph = morphlib.morphology.Morphology(f, 
                                               self.settings['git-base-url'])
        return morph

