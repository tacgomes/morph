# Copyright (C) 2012-2013  Codethink Limited
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
import os

import morphlib


class BuildEnvironment():

    def __init__(self, settings, target, arch=None):
        '''Create a new BuildEnvironment object'''

        self.extra_path = []
        self.target = target
        self.arch = morphlib.util.arch() if arch is None else arch
        self.env = self._clean_env(settings)

    _osenv = os.environ
    _ccache_path = '/usr/lib/ccache'
    _override_home = '/tmp'
    _override_locale = 'C'
    _override_shell = '/bin/sh'
    _override_term = 'dumb'
    _override_username = 'tomjon'

    def get_bootstrap_target(self, target):
        '''Set 'vendor' field of the given machine triplet as 'bootstrap' '''

        parts = target.split('-')
        if len(parts) < 2:
            raise morphlib.Error('Failed to parse machine triplet returned by '
                                 'host compiler: %s' % target)
        return '-'.join([parts[0], 'bootstrap'] + parts[2:])

    def _clean_env(self, settings):
        '''Create a fresh set of environment variables for a clean build.

        Return a dict with the new environment.

        '''

        # copy a set of white-listed variables from the original env
        copied_vars = dict.fromkeys([
            'DISTCC_HOSTS',
            'LD_PRELOAD',
            'LD_LIBRARY_PATH',
            'FAKEROOTKEY',
            'FAKED_MODE',
            'FAKEROOT_FD_BASE',
        ])
        for name in copied_vars:
            copied_vars[name] = self._osenv.get(name, None)

        env = {}

        # apply the copied variables to the clean env
        for name in copied_vars:
            if copied_vars[name] is not None:
                env[name] = copied_vars[name]

        env['TERM'] = self._override_term
        env['SHELL'] = self._override_shell
        env['USER'] = \
            env['USERNAME'] = \
            env['LOGNAME'] = self._override_username
        env['LC_ALL'] = self._override_locale
        env['HOME'] = self._override_home

        env['PREFIX'] = settings['prefix']
        env['BUILD'] = self.target
        env['TARGET'] = self.target
        env['TARGET_STAGE1'] = self.get_bootstrap_target(self.target)
        env['TARGET_GCC_CONFIG'] = ''

        if not settings['no-ccache']:
            self.extra_path.append(self._ccache_path)

# FIXME: we should set CCACHE_BASEDIR so any objects that refer to their
#        current directory get corrected. This improve the cache hit rate
#            env['CCACHE_BASEDIR'] = self.tempdir.dirname
            env['CCACHE_DIR'] = '/tmp/ccache'
            env['CCACHE_EXTRAFILES'] = ':'.join(
                f for f in ('/baserock/binutils.meta',
                            '/baserock/eglibc.meta',
                            '/baserock/gcc.meta') if os.path.exists(f)
            )
            if not settings['no-distcc']:
                env['CCACHE_PREFIX'] = 'distcc'

        return env
