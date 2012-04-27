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


import errno
import logging
import os
import shutil
import tarfile

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
    
    def __init__(self, dirname, tempdir):
        self.dirname = dirname
        self.tempdir = tempdir

    # Wrapper to be overridden by unit tests.
    def _mkdir(self, dirname): # pragma: no cover
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
        return filename[len(dirname)-1:] # include leading slash

    def install_artifact(self, handle):
        '''Install a build artifact into the staging area.
        
        We access the artifact via an open file handle. For now, we assume
        the artifact is a tarball.
        
        '''

        logging.debug('Installing artifact %s' % 
                        getattr(handle, 'name', 'unknown name'))        
        tf = tarfile.open(fileobj=handle)
        
        # This is evil, but necessary. For some reason Python's system
        # call wrappers (os.mknod and such) do not (always?) set the
        # filename attribute of the OSError exception they raise. We
        # fix that by monkey patching the tf instance with wrappers
        # for the relevant methods to add things. The wrapper further
        # ignores EEXIST errors, since we do not (currently!) care about
        # overwriting files.
        
        def monkey_patcher(real):
            def make_something(tarinfo, targetpath): # pragma: no cover
                if os.path.exists(targetpath):
                    try:     os.remove(targetpath)
                    except:  pass
                try:
                    return real(tarinfo, targetpath)
                except OSError, e:
                    if e.errno != errno.EEXIST:
                        if e.filename is None:
                            e.filename = targetpath
                            raise e
                        else:
                            raise
            return make_something

        tf.makedir = monkey_patcher(tf.makedir)
        tf.makefile = monkey_patcher(tf.makefile)
        tf.makeunknown = monkey_patcher(tf.makeunknown)
        tf.makefifo = monkey_patcher(tf.makefifo)
        tf.makedev = monkey_patcher(tf.makedev)
        tf.makelink = monkey_patcher(tf.makelink)

        tf.extractall(path=self.dirname)

    def remove(self):
        '''Remove the entire staging area.
        
        Do not expect anything with the staging area to work after this
        method is called. Be careful about calling this method if
        the filesystem root directory was given as the dirname.
        
        '''
        
        shutil.rmtree(self.dirname)

    def runcmd(self, argv, **kwargs): # pragma: no cover
        '''Run a command in a chroot in the staging area.'''
        ex = morphlib.execute.Execute('/', logging.debug)
        cwd = kwargs.get('cwd') or '/'
        if 'cwd' in kwargs:
            cwd = kwargs['cwd']
            del kwargs['cwd']
        else:
            cwd = '/'
        real_argv = ['chroot', self.dirname, 'sh', '-c',
                     'cd "$1" && shift && exec "$@"', '--', cwd] + argv
        return ex.runv(real_argv, **kwargs)

