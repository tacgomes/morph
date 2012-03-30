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


class BuildSystem(object):

    '''An abstraction of an upstream build system.
    
    Some build systems are well known: autotools, for example.
    Others are purely manual: there's a set of commands to run that
    are specific for that project, and (almost) no other project uses them.
    The Linux kernel would be an example of that.
    
    This class provides an abstraction for these, including a method
    to autodetect well known build systems.
    
    '''
    
    def used_by_project(self, srcdir):
        '''Does project at ``srcdir`` use this build system?'''
        raise NotImplementedError() # pragma: no cover
    

class ManualBuildSystem(BuildSystem):

    '''A manual build system where the morphology must specify all commands.'''
    
    def used_by_project(self, srcdir):
        return False

class AutotoolsBuildSystem(BuildSystem):

    '''The automake/autoconf/libtool holy trinity.'''

