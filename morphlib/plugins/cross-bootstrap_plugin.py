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

import cliapp
import logging
import os.path
import re
import tarfile
import traceback

import morphlib

driver_header = '''#!/bin/sh
echo "Morph native bootstrap script"
echo "Generated by Morph version %s\n"

set -eu

export PATH=/tools/bin:$PATH
export SRCDIR=/src

''' % morphlib.__version__

driver_footer = '''

echo "Complete!"
echo "Bootstrapped system rootfs is in $DESTDIR."
'''

def escape_source_name(source):
    repo_name = source.repo.original_name
    ref = source.original_ref
    source_name = '%s__%s' % (repo_name, ref)
    return re.sub(':/', '_', source_name)

# Most of this is ripped from RootfsTarballBuilder, and should be reconciled
# with it.
class BootstrapSystemBuilder(morphlib.builder2.BuilderBase):
    '''Build a bootstrap system tarball
    
       The bootstrap system image contains a minimal cross-compiled toolchain
       and a set of extracted sources for the rest of the system, with shell
       scripts to run the required morphology commands. This allows new
       architectures to be bootstrapped without needing to build Python, Git,
       Perl and all of Morph's other dependencies first.
    '''

    def build_and_cache(self):
        with self.build_watch('overall-build'):
            handle = self.local_artifact_cache.put(self.artifact)
            fs_root = self.staging_area.destdir(self.artifact.source)
            try:
                self.unpack_binary_chunks(fs_root)
                self.unpack_sources(fs_root)
                self.write_build_script(fs_root)
                system_name = self.artifact.source.morphology['name']
                self.create_tarball(handle, fs_root, system_name)
            except BaseException, e:
                logging.error(traceback.format_exc())
                self.app.status(msg='Error while building bootstrap image',
                                error=True)
                handle.abort()
                raise

            handle.close()

        self.save_build_times()
        return [self.artifact]

    def unpack_binary_chunks(self, dest):
        cache = self.local_artifact_cache
        for chunk_artifact in self.artifact.source.cross_chunks:
            with cache.get(chunk_artifact) as chunk_file:
                try:
                    morphlib.bins.unpack_binary_from_file(chunk_file, dest)
                except BaseException, e:
                    self.app.status(
                        msg='Error unpacking binary chunk %(name)s',
                        name=chunk_artifact.name,
                        error=True)
                    raise

    def unpack_sources(self, path):
        # Multiple chunks sources may be built from the same repo ('linux'
        # and 'linux-api-headers' are a good example), so we check out the
        # sources once per repository.
        #
        # It might be neater to build these as "source artifacts" individually,
        # but that would waste huge amounts of space in the artifact cache.
        for a in self.artifact.walk():
            if a in self.artifact.source.cross_chunks:
                continue
            if a.source.morphology['kind'] != 'chunk':
                continue

            escaped_source = escape_source_name(a.source)
            source_dir = os.path.join(path, 'src', escaped_source)
            if not os.path.exists(source_dir):
                os.makedirs(source_dir)
                morphlib.builder2.extract_sources(
                    self.app, self.repo_cache, a.source.repo, a.source.sha1,
                    source_dir)

            name = a.source.morphology['name']
            chunk_script = os.path.join(path, 'src', 'build-%s' % name)
            with morphlib.savefile.SaveFile(chunk_script, 'w') as f:
                self.write_chunk_build_script(a, f)
            os.chmod(chunk_script, 0777)

    def write_build_script(self, path):
        '''Output a script to run build on the bootstrap target'''

        driver_script = os.path.join(path, 'native-bootstrap')
        with morphlib.savefile.SaveFile(driver_script, 'w') as f:
            f.write(driver_header)

            f.write('echo Setting up build environment...\n')
            for k,v in self.staging_area.env.iteritems():
                f.write('export %s="%s"\n' % (k, v))

            # FIXME: really, of course, we need to iterate the sources not the
            # artifacts ... this will break when we have chunk splitting!
            for a in self.artifact.walk():
                if a in self.artifact.source.cross_chunks:
                    continue
                if a.source.morphology['kind'] != 'chunk':
                    continue

                name = a.source.morphology['name']
                f.write('\necho Building %s\n' % name)
                f.write('$SRCDIR/build-%s\n' % name)

            f.write(driver_footer)
        os.chmod(driver_script, 0777)

    def write_chunk_build_script(self, chunk, f):
        m = chunk.source.morphology
        f.write('#!/bin/sh\n')
        f.write('# Build script generated by morph\n')
        f.write('chunk_name=%s\n' % m['name'])

        repo = escape_source_name(chunk.source)
        f.write('cp -a $SRCDIR/%s $DESTDIR/$chunk_name.build\n' % repo)
        f.write('cd $DESTDIR/$chunk_name.build\n')
        f.write('export PREFIX=%s\n' % chunk.source.prefix)

        bs = morphlib.buildsystem.lookup_build_system(m['build-system'])

        # FIXME: merge some of this with Morphology
        steps = [
            ('pre-configure', False),
            ('configure', False),
            ('post-configure', False),
            ('pre-build', True),
            ('build', True),
            ('post-build', True),
            ('pre-test', False),
            ('test', False),
            ('post-test', False),
            ('pre-install', False),
            ('install', False),
            ('post-install', False),
        ]
        
        for step, in_parallel in steps:
            key = '%s-commands' % step
            cmds = m.get_commands(key)
            for cmd in cmds:
                if in_parallel:
                    max_jobs = m['max-jobs']
                    if max_jobs is None:
                        max_jobs = self.max_jobs
                    f.write('MAKEFLAGS=-j%s ' % max_jobs)
                f.write(cmd + '\n')

        f.write('rm -Rf $DESTDIR/$chunk_name.build')

    def create_tarball(self, handle, fs_root, system_name):
        unslashy_root = fs_root[1:]
        def uproot_info(info):
            info.name = os.path.relpath(info.name, unslashy_root)
            if info.islnk():
                info.linkname = os.path.relpath(info.linkname, unslashy_root)
            return info

        tar = tarfile.TarFile.gzopen(fileobj=handle, mode="w",
                                     compresslevel=1,
                                     name=system_name)
        self.app.status(msg='Constructing tarball of root filesystem',
                        chatty=True)
        tar.add(fs_root, recursive=True, filter=uproot_info)
        tar.close()


class CrossBootstrapPlugin(cliapp.Plugin):

    def enable(self):
        self.app.add_subcommand('cross-bootstrap',
                                self.cross_bootstrap,
                                arg_synopsis='TARGET REPO REF SYSTEM-MORPH')

    def disable(self):
        pass

    def cross_bootstrap(self, args):
        '''Cross-bootstrap a system from a different architecture.'''

        # A brief overview of this process: the goal is to native build as much
        # of the system as possible because that's easier, but in order to do
        # so we need at least 'build-essential'. 'morph cross-bootstrap' will
        # cross-build any bootstrap-mode chunks in the given system and
        # will then prepare a large rootfs tarball which, when booted, will
        # build the rest of the chunks in the system using the cross-built
        # build-essential.
        #
        # This approach saves us from having to run Morph, Git, Python, Perl,
        # or anything else complex and difficult to cross-build on the target
        # until it is bootstrapped. The user of this command needs to provide
        # a kernel and handle booting the system themselves (the generated
        # tarball contains a /bin/sh that can be used as 'init'.
        #
        # This function is a variant of the BuildCommand() class in morphlib.

        # To do: make it work on a system branch instead of repo/ref/morph
        # triplet.

        if len(args) < 4:
            raise cliapp.AppException(
                'cross-bootstrap requires 4 arguments: target archicture, and '
                'repo, ref and and name of the system morphology')

        arch = args[0]
        root_repo, ref, system_name = args[1:4]

        if arch not in morphlib.valid_archs:
            raise morphlib.Error('Unsupported architecture "%s"' % arch)

        # Get system artifact

        build_env = morphlib.buildenvironment.BuildEnvironment(
            self.app.settings, arch)
        build_command = morphlib.buildcommand.BuildCommand(self.app, build_env)

        morph_name = system_name + '.morph'
        builds_artifacts = [system_name + '-bootstrap-rootfs']
        srcpool = build_command.create_source_pool(root_repo, ref, morph_name)

        system_source = srcpool.lookup(root_repo, ref, morph_name)
        system_source.morphology.builds_artifacts = builds_artifacts

        system_artifact = build_command.resolve_artifacts(srcpool)

        # Calculate build order
        # This is basically a hacked version of BuildCommand.build_in_order()
        artifacts = system_artifact.walk()
        cross_chunks = []
        native_chunks = []
        for a in artifacts:
            if a.source.morphology['kind'] == 'chunk':
                if a.source.build_mode == 'bootstrap':
                    cross_chunks.append(a)
                else:
                    native_chunks.append(a)

        if len(cross_chunks) == 0:
            raise morphlib.Error(
                'Nothing to cross-compile. Only chunks built in \'bootstrap\' '
                'mode can be cross-compiled.')

        # FIXME: merge with build-command's code
        for i, a in enumerate(cross_chunks):
            if build_command.is_built(a):
                self.app.status(msg='The %(kind)s %(name)s is already built',
                                kind=a.source.morphology['kind'],
                                name=a.name)
                build_command.cache_artifacts_locally([a])
            else:
                self.app.status(msg='Cross-building %(kind)s %(name)s',
                                kind=a.source.morphology['kind'],
                                name=a.name)
                build_command.build_artifact(a, build_env)

        for i, a in enumerate(native_chunks):
            build_command.get_sources(a)

        # Install those to the output tarball ...
        self.app.status(msg='Building final bootstrap system image')
        system_artifact.source.cross_chunks = cross_chunks
        staging_area = build_command.create_staging_area(
            build_env, use_chroot=False)
        builder = BootstrapSystemBuilder(
            self.app, staging_area, build_command.lac, build_command.rac,
            system_artifact, build_command.lrc, 1, False)
        builder.build_and_cache()

        self.app.status(
            msg='Bootstrap tarball for %(name)s is cached at %(cachepath)s',
            name=system_artifact.name,
            cachepath=build_command.lac.artifact_filename(system_artifact))
