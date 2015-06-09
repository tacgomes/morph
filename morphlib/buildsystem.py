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

    '''Predefined commands for common build systems.

    Some build systems are well known: autotools, for example. We provide
    pre-defined build commands for these so that they don't need to be copied
    and pasted many times in the build instructions.

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


class ManualBuildSystem(BuildSystem):

    '''A manual build system where the morphology must specify all commands.'''

    name = 'manual'


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


class AutotoolsBuildSystem(BuildSystem):

    '''The automake/autoconf/libtool holy trinity.'''

    name = 'autotools'

    def __init__(self):
        BuildSystem.__init__(self)
        self.configure_commands = [
            'export NOCONFIGURE=1; ' +
            'if [ -e autogen ]; then ./autogen; ' +
            'elif [ -e autogen.sh ]; then ./autogen.sh; ' +
            'elif [ -e bootstrap ]; then ./bootstrap; ' +
            'elif [ -e bootstrap.sh ]; then ./bootstrap.sh; ' +
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


class ExtUtilsMakeMakerBuildSystem(BuildSystem):

    '''The ExtUtils::MakeMaker build system.

    To install perl distributions into the correct location in our chroot
    we need to set PREFIX to <destdir>/<prefix> in the configure-commands.

    The mapping between PREFIX and the final installation
    directories is complex and depends upon the configuration of perl
    see,
    https://metacpan.org/pod/distribution/perl/INSTALL#Installation-Directories
    and ExtUtil::MakeMaker's documentation for more details.

    '''

    # This is called the 'cpan' build system for historical reasons,
    # back when morph only supported one of the perl build systems.
    name = 'cpan'

    def __init__(self):
        BuildSystem.__init__(self)

        self.configure_commands = [
            'perl Makefile.PL PREFIX=$DESTDIR$PREFIX',
        ]
        self.build_commands = [
            'make',
        ]
        self.test_commands = [
            # FIXME: we ought to run tests by default,
            # and use chunk morphs to disable for special cases
            # 'make test',
        ]
        self.install_commands = [
            'make install',
        ]
        self.strip_commands = [_STRIP_COMMAND]



class ModuleBuildBuildSystem(BuildSystem):

    '''The Module::Build build system'''

    name = 'module-build'

    def __init__(self):
        super(ModuleBuildBuildSystem, self).__init__()

        self.configure_commands = [
            # See the comment in ExtUtilsMakeMakerBuildSystem
            # to see why --prefix is set to $DESTDIR$PREFIX here,
            # (--prefix in Module::Build has the same meaning
            #  as PREFIX in ExtUtils::MakeMaker)
            'perl Build.PL --prefix "$DESTDIR$PREFIX"'
        ]

        self.build_commands = [
            './Build'
        ]

        self.test_commands = [
            './Build test'
        ]

        self.install_commands =  [
            './Build install'
        ]


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


build_systems = [
    ManualBuildSystem(),
    AutotoolsBuildSystem(),
    PythonDistutilsBuildSystem(),
    ExtUtilsMakeMakerBuildSystem(),
    ModuleBuildBuildSystem(),
    CMakeBuildSystem(),
    QMakeBuildSystem(),
    DummyBuildSystem(),
]


def lookup_build_system(name):
    '''Return build system that corresponds to the name.

    If the name does not match any build system, raise ``KeyError``.

    '''

    for bs in build_systems:
        if bs.name == name:
            return bs
    raise KeyError('Unknown build system: %s' % name)
