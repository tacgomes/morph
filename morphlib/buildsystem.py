# Copyright (C) 2012-2015  Codethink Limited
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
# with this program.  If not, see <http://www.gnu.org/licenses/>.


import os

import morphlib


# TODO: Make idempotent when files are hardlinks
# Strip all ELF binary files that are executable or named like a library.
# .so files for C, .cmxs for OCaml and .node for Node.
# The file name and permissions checks are done with the `find` command before
# the ELF header is checked with the shell command, because it is a lot cheaper
# to check the mode and file name first, because it is a metadata check, rather
# than a subprocess and a file read.
# `file` is not used, to keep the dependency requirements down.
_STRIP_COMMAND = r'''find "$DESTDIR" -type f \
  '(' -perm -111 -o -name '*.so*' -o -name '*.cmxs' -o -name '*.node' ')' \
  -exec sh -ec \
  'read -n4 hdr <"$1" # check for elf header
   if [ "$hdr" != "$(printf \\x7fELF)" ]; then
       exit 0
   fi
   debugfile="$DESTDIR$PREFIX/lib/debug/$(basename "$1")"
   mkdir -p "$(dirname "$debugfile")"
   objcopy --only-keep-debug "$1" "$debugfile"
   chmod 644 "$debugfile"
   strip --remove-section=.comment --remove-section=.note --strip-unneeded "$1"
   objcopy --add-gnu-debuglink "$debugfile" "$1"' - {} ';'
'''


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
        self.pre_configure_commands = []
        self.configure_commands = []
        self.post_configure_commands = []
        self.pre_build_commands = []
        self.build_commands = []
        self.post_build_commands = []
        self.pre_test_commands = []
        self.test_commands = []
        self.post_test_commands = []
        self.pre_install_commands = []
        self.install_commands = []
        self.post_install_commands = []
        self.pre_strip_commands = []
        self.strip_commands = []
        self.post_strip_commands = []

    def __getitem__(self, key):
        key = '_'.join(key.split('-'))
        return getattr(self, key)

    def get_morphology(self, name):
        '''Return the text of an autodetected chunk morphology.'''

        return morphlib.morphology.Morphology({
            'name': name,
            'kind': 'chunk',
            'build-system': self.name,
        })

    def used_by_project(self, file_list):
        '''Does a project use this build system?

        ``exists`` is a function that returns a boolean telling if a
        filename, relative to the project source directory, exists or not.

        '''
        raise NotImplementedError()  # pragma: no cover


class ManualBuildSystem(BuildSystem):

    '''A manual build system where the morphology must specify all commands.'''

    name = 'manual'

    def used_by_project(self, file_list):
        return False


class DummyBuildSystem(BuildSystem):

    '''A dummy build system, useful for debugging morphologies.'''

    name = 'dummy'

    def __init__(self):
        BuildSystem.__init__(self)
        self.configure_commands = ['echo dummy configure']
        self.build_commands = ['echo dummy build']
        self.test_commands = ['echo dummy test']
        self.install_commands = ['echo dummy install']
        self.strip_commands = ['echo dummy strip']

    def used_by_project(self, file_list):
        return False


class AutotoolsBuildSystem(BuildSystem):

    '''The automake/autoconf/libtool holy trinity.'''

    name = 'autotools'

    def __init__(self):
        BuildSystem.__init__(self)
        self.configure_commands = [
            'export NOCONFIGURE=1; ' +
            'if [ -e autogen ]; then ./autogen; ' +
            'elif [ -e autogen.sh ]; then ./autogen.sh; ' +
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
        self.strip_commands = [_STRIP_COMMAND]

    def used_by_project(self, file_list):
        indicators = [
            'autogen',
            'autogen.sh',
            'configure',
            'configure.ac',
            'configure.in',
            'configure.in.in',
        ]

        return any(x in file_list for x in indicators)


class PythonDistutilsBuildSystem(BuildSystem):

    '''The Python distutils build systems.'''

    name = 'python-distutils'

    def __init__(self):
        BuildSystem.__init__(self)
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
        self.strip_commands = [_STRIP_COMMAND]

    def used_by_project(self, file_list):
        indicators = [
            'setup.py',
        ]

        return any(x in file_list for x in indicators)


class ExtUtilsMakeMakerBuildSystem(BuildSystem):

    '''The Perl cpan build system.'''

    name = 'cpan'

    def __init__(self):
        BuildSystem.__init__(self)
        self.configure_commands = [
            'perl Makefile.PL INSTALLDIRS=perl '
            'INSTALLARCHLIB="$PREFIX/lib/perl" '
            'INSTALLPRIVLIB="$PREFIX/lib/perl" '
            'INSTALLBIN="$PREFIX/bin" '
            'INSTALLSCRIPT="$PREFIX/bin" '
            'INSTALLMAN1DIR="$PREFIX/share/man/man1" '
            'INSTALLMAN3DIR="$PREFIX/share/man/man3"',
        ]
        self.build_commands = [
            'make',
        ]
        self.test_commands = [
        ]
        self.install_commands = [
            'make DESTDIR="$DESTDIR" install',
        ]
        self.strip_commands = [_STRIP_COMMAND]

    def used_by_project(self, file_list):
        indicators = [
            'Makefile.PL',
        ]

        return any(x in file_list for x in indicators)

class CMakeBuildSystem(BuildSystem):

    '''The cmake build system.'''

    name = 'cmake'

    def __init__(self):
        BuildSystem.__init__(self)
        self.configure_commands = [
            'cmake -DCMAKE_INSTALL_PREFIX=/usr'
         ]
        self.build_commands = [
            'make',
        ]
        self.test_commands = [
        ]
        self.install_commands = [
            'make DESTDIR="$DESTDIR" install',
        ]
        self.strip_commands = [_STRIP_COMMAND]

    def used_by_project(self, file_list):
        indicators = [
            'CMakeLists.txt',
        ]

        return any(x in file_list for x in indicators)

class QMakeBuildSystem(BuildSystem):

    '''The Qt build system.'''

    name = 'qmake'

    def __init__(self):
        BuildSystem.__init__(self)
        self.configure_commands = [
            'qmake -makefile '
        ]
        self.build_commands = [
            'make',
        ]
        self.test_commands = [
        ]
        self.install_commands = [
            'make INSTALL_ROOT="$DESTDIR" install',
        ]
        self.strip_commands = [_STRIP_COMMAND]

    def used_by_project(self, file_list):
        indicator = '.pro'

        for x in file_list:
            if x.endswith(indicator):
                return True
            
        return False

build_systems = [
    ManualBuildSystem(),
    AutotoolsBuildSystem(),
    PythonDistutilsBuildSystem(),
    ExtUtilsMakeMakerBuildSystem(),
    CMakeBuildSystem(),
    QMakeBuildSystem(),
    DummyBuildSystem(),
]


def detect_build_system(file_list):
    '''Automatically detect the build system, if possible.

    If the build system cannot be detected automatically, return None.
    For ``exists`` see the ``BuildSystem.exists`` method.

    '''
    for bs in build_systems:
        if bs.used_by_project(file_list):
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
