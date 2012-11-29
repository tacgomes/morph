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


import logging
import os
import shutil

import morphlib


class StagingArea(object):

    '''Represent the staging area for building software.

    The build dependencies of what will be built will be installed in the
    staging area. The staging area may be a dedicated part of the
    filesystem, used with chroot, or it can be the actual root of the
    filesystem, which is needed when bootstrap building Baserock. The
    caller chooses this by providing the root directory of the staging
    area when the object is created. The directory must already exist.

    The staging area can also install build artifacts.

    '''

    def __init__(self, app, dirname, tempdir):
        self._app = app
        self.dirname = dirname
        self.tempdir = tempdir
        self.builddirname = None
        self.destdirname = None        

    # Wrapper to be overridden by unit tests.
    def _mkdir(self, dirname):  # pragma: no cover
        os.mkdir(dirname)

    def _dir_for_source(self, source, suffix):
        dirname = os.path.join(self.tempdir,
                               '%s.%s' % (source.morphology['name'], suffix))
        self._mkdir(dirname)
        return dirname

    def builddir(self, source):
        '''Create a build directory for a given source project.

        Return path to directory.

        '''

        return self._dir_for_source(source, 'build')

    def destdir(self, source):
        '''Create an installation target directory for a given source project.

        This is meant to be used as $DESTDIR when installing chunks.
        Return path to directory.

        '''

        return self._dir_for_source(source, 'inst')

    def relative(self, filename):
        '''Return a filename relative to the staging area.'''

        dirname = self.dirname
        if not dirname.endswith('/'):
            dirname += '/'

        assert filename.startswith(dirname)
        return filename[len(dirname) - 1:]  # include leading slash

    def install_artifact(self, handle):
        '''Install a build artifact into the staging area.

        We access the artifact via an open file handle. For now, we assume
        the artifact is a tarball.

        '''

        logging.debug('Installing artifact %s' %
                      getattr(handle, 'name', 'unknown name'))

        unpacked_artifact = os.path.join(
            self._app.settings['cachedir'],
            'artifacts',
            os.path.basename(handle.name) + '.d')
        if not os.path.exists(unpacked_artifact):
            self._mkdir(unpacked_artifact)
            morphlib.bins.unpack_binary_from_file(
                handle, unpacked_artifact + '/')
            
        if not os.path.exists(self.dirname):
            self._mkdir(self.dirname)

        self._app.runcmd(
            ['cp', '-al', unpacked_artifact + '/.', self.dirname + '/.'])

    def remove(self):
        '''Remove the entire staging area.

        Do not expect anything with the staging area to work after this
        method is called. Be careful about calling this method if
        the filesystem root directory was given as the dirname.

        '''

        shutil.rmtree(self.dirname)

    def chroot_open(self, source): # pragma: no cover
        '''Setup staging area for use as a chroot.'''

        assert self.builddirname == None and self.destdirname == None

        builddir = self.builddir(source)
        destdir = self.destdir(source)
        self.builddirname = self.relative(builddir).lstrip('/')
        self.destdirname = self.relative(destdir).lstrip('/')

        for mount_point in ['proc','dev/shm']:
            path = os.path.join(self.dirname, mount_point)
            if not os.path.exists(path):
                os.makedirs(path)

        return builddir, destdir

    def chroot_close(self): # pragma: no cover
        '''Undo changes by chroot_open.
        
        This should be called after the staging area is no longer needed.
        
        '''

    def runcmd(self, argv, **kwargs):  # pragma: no cover
        '''Run a command in the staging area.'''

        cwd = kwargs.get('cwd') or '/'
        if 'cwd' in kwargs:
            cwd = kwargs['cwd']
            del kwargs['cwd']
        else:
            cwd = '/'

        if self._app.settings['staging-chroot']:
            entries = os.listdir(self.dirname)

            friends = [self.builddirname, self.destdirname,
                       'dev', 'proc', 'tmp']
            for friend in friends:
                if friend in friends:
                    entries.remove(friend)

            real_argv = ['linux-user-chroot']

            for entry in entries:
                real_argv += ['--mount-readonly',"/"+entry]
            
            real_argv += ['--mount-proc','/proc']
            real_argv += ['--mount-bind','/dev/shm','/dev/shm']
            real_argv += [self.dirname]
        else:
            real_argv = ['chroot', '/']

        real_argv += ['sh', '-c', 'cd "$1" && shift && exec "$@"', '--', cwd]
        real_argv += argv

        return self._app.runcmd(real_argv, **kwargs)
