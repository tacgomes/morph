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


import os


class BuildSystem(object):

    '''An abstraction of an upstream build system.
    
    Some build systems are well known: autotools, for example.
    Others are purely manual: there's a set of commands to run that
    are specific for that project, and (almost) no other project uses them.
    The Linux kernel would be an example of that.
    
    This class provides an abstraction for these, including a method
    to autodetect well known build systems.
    
    '''
    
    def __init__(self):
        self.configure_commands = []
        self.build_commands = []
        self.test_commands = []
        self.install_commands = []
        
    def __getitem__(self, key):
        key = '_'.join(key.split('-'))
        return getattr(self, key)
        
    def get_morphology_text(self, name):
        '''Return the text of an autodetected chunk morphology.'''
        
        return '''
            {
                "name": "%(name)s",
                "kind": "chunk",
                "build-system": "%(bs)s"
            }
        ''' % {
            'name': name,
            'bs': self.name,
        }
    
    def used_by_project(self, exists):
        '''Does a project use this build system?
        
        ``exists`` is a function that returns a boolean telling if a
        filename, relative to the project source directory, exists or not.
        
        '''
        raise NotImplementedError() # pragma: no cover
        

class ManualBuildSystem(BuildSystem):

    '''A manual build system where the morphology must specify all commands.'''

    name = 'manual'
    
    def used_by_project(self, exists):
        return False


class DummyBuildSystem(BuildSystem):

    '''A dummy build system, useful for debugging morphologies.'''

    name = 'dummy'
    
    def __init__(self):
        self.configure_commands = ['echo dummy configure']
        self.build_commands = ['echo dummy build']
        self.test_commands = ['echo dummy test']
        self.install_commands = ['echo dummy install']

    def used_by_project(self, exists):
        return False


class AutotoolsBuildSystem(BuildSystem):

    '''The automake/autoconf/libtool holy trinity.'''

    name = 'autotools'
    
    def __init__(self):
        self.configure_commands = [
            'if [ -e autogen.sh ]; then ./autogen.sh; ' +
            'elif [ ! -e ./configure ]; then autoreconf -ivf; fi',
            './configure --prefix="$PREFIX"',
        ]
        self.build_commands = [
            'make',
        ]
        self.test_commands = [
        ]
        self.install_commands = [
            'make DESTDIR="$DESTDIR" install',
        ]

    def used_by_project(self, exists):
        indicators = [
            'autogen.sh',
            'configure',
            'configure.ac',
            'configure.in',
            'configure.in.in',
        ]
        
        return any(exists(x) for x in indicators)


class PythonDistutilsBuildSystem(BuildSystem):

    '''The Python distutils build systems.'''

    name = 'python-distutils'
    
    def __init__(self):
        self.configure_commands = [
        ]
        self.build_commands = [
            'python setup.py build',
        ]
        self.test_commands = [
        ]
        self.install_commands = [
            'python setup.py install --prefix "$PREFIX" --root "$DESTDIR"',
        ]

    def used_by_project(self, exists):
        indicators = [
            'setup.py',
        ]
        
        return any(exists(x) for x in indicators)


class PerlBuildSystem(BuildSystem):

    '''The Perl build system.'''

    name = 'perl'

    def __init__(self):
        self.configure_commands = [
            'perl Makefile.PL',
        ]
        self.build_commands = [
            'make',
        ]
        self.test_commands = [
        ]
        self.install_commands = [
            'make install',
        ]

    def used_by_project(self, exists):
        indicators = [
            'Makefile.PL',
        ]

        return any(exists(x) for x in indicators)


build_systems = [
    ManualBuildSystem(),
    AutotoolsBuildSystem(),
    PythonDistutilsBuildSystem(),
    PerlBuildSystem(),
    DummyBuildSystem(),
]


def detect_build_system(exists):
    '''Automatically detect the build system, if possible.
    
    If the build system cannot be detected automatically, return None.
    For ``exists`` see the ``BuildSystem.exists`` method.
    
    '''
    
    for bs in build_systems:
        if bs.used_by_project(exists):
            return bs
    return None


def lookup_build_system(name):
    '''Return build system that corresponds to the name.
    
    If the name does not match any build system, raise ``KeyError``.
    
    '''
    
    for bs in build_systems:
        if bs.name == name:
            return bs
    raise KeyError('Unknown build system: %s' % name)

