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


import shutil
import tarfile


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
    
    def __init__(self, dirname):
        self.dirname = dirname

    def install_artifact(self, handle):
        '''Install a build artifact into the staging area.
        
        We access the artifact via an open file handle. For now, we assume
        the artifact is a tarball.
        
        '''
        
        tf = tarfile.TarFile(fileobj=handle)
        tf.extractall(path=self.dirname)

    def remove(self):
        '''Remove the entire staging area.
        
        Do not expect anything with the staging area to work after this
        method is called. Be careful about calling this method if
        the filesystem root directory was given as the dirname.
        
        '''
        
        shutil.rmtree(self.dirname)

