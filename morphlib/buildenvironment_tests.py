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


import copy
import unittest

import morphlib
from morphlib import buildenvironment


class BuildEnvironmentTests(unittest.TestCase):

    def setUp(self):
        self.settings = {
            'prefix': '/usr',
            'no-ccache': True,
            'no-distcc': True
        }
        self.fake_env = {
            'PATH': '/fake_bin',
        }

    def new_build_env(self, settings=None, target=None, **kws):
        settings = settings or self.settings
        target = target or self.target
        return buildenvironment.BuildEnvironment(settings, target, **kws)

    def new_build_env(self, settings=None, arch='x86_64'):
        settings = settings or self.settings
        return buildenvironment.BuildEnvironment(settings, arch)

    def test_copies_whitelist_vars(self):
        env = self.fake_env
        safe = {
            'DISTCC_HOSTS': 'example.com:example.co.uk',
            'LD_PRELOAD': '/buildenv/lib/libbuildenv.so',
            'LD_LIBRARY_PATH': '/buildenv/lib:/buildenv/lib64',
            'FAKEROOTKEY': 'b011de73',
            'FAKED_MODE': 'non-fakeroot',
            'FAKEROOT_FD_BASE': '-1',
        }
        env.update(safe)
        old_osenv = buildenvironment.BuildEnvironment._osenv
        buildenvironment.BuildEnvironment._osenv = env

        buildenv = self.new_build_env()
        self.assertEqual(sorted(safe.items()),
                         sorted([(k, buildenv.env[k]) for k in safe.keys()]))

        buildenvironment.BuildEnvironment._osenv = old_osenv

    def test_user_spellings_equal(self):
        buildenv = self.new_build_env()
        self.assertTrue(buildenv.env['USER'] == buildenv.env['USERNAME'] ==
                        buildenv.env['LOGNAME'])

    def test_environment_overrides(self):
        buildenv = self.new_build_env()
        self.assertEqual(buildenv.env['TERM'], buildenv._override_term)
        self.assertEqual(buildenv.env['SHELL'], buildenv._override_shell)
        self.assertEqual(buildenv.env['USER'], buildenv._override_username)
        self.assertEqual(buildenv.env['USERNAME'], buildenv._override_username)
        self.assertEqual(buildenv.env['LOGNAME'], buildenv._override_username)
        self.assertEqual(buildenv.env['LC_ALL'], buildenv._override_locale)
        self.assertEqual(buildenv.env['HOME'], buildenv._override_home)

    def test_arch_x86_64(self):
        b = self.new_build_env(arch='x86_64')
        self.assertEqual(b.env['MORPH_ARCH'], 'x86_64')
        self.assertEqual(b.env['TARGET'], 'x86_64-baserock-linux-gnu')
        self.assertEqual(b.env['TARGET_STAGE1'], 'x86_64-bootstrap-linux-gnu')

    def test_arch_x86_32(self):
        b = self.new_build_env(arch='x86_32')
        self.assertEqual(b.env['MORPH_ARCH'], 'x86_32')
        self.assertEqual(b.env['TARGET'], 'i686-baserock-linux-gnu')
        self.assertEqual(b.env['TARGET_STAGE1'], 'i686-bootstrap-linux-gnu')

    def test_arch_armv7l(self):
        b = self.new_build_env(arch='armv7l')
        self.assertEqual(b.env['MORPH_ARCH'], 'armv7l')
        self.assertEqual(b.env['TARGET'], 'armv7l-baserock-linux-gnueabi')
        self.assertEqual(b.env['TARGET_STAGE1'],
                         'armv7l-bootstrap-linux-gnueabi')

    def test_arch_armv7b(self):
        b = self.new_build_env(arch='armv7b')
        self.assertEqual(b.env['MORPH_ARCH'], 'armv7b')
        self.assertEqual(b.env['TARGET'], 'armv7b-baserock-linux-gnueabi')
        self.assertEqual(b.env['TARGET_STAGE1'],
                         'armv7b-bootstrap-linux-gnueabi')

    def test_ccache_vars_set(self):
        new_settings = copy.copy(self.settings)
        new_settings['no-ccache'] = False
        new_settings['no-distcc'] = False
        buildenv = self.new_build_env(settings=new_settings)
        self.assertTrue(buildenv._ccache_path in buildenv.extra_path)
        self.assertEqual(buildenv.env['CCACHE_PREFIX'], 'distcc')
