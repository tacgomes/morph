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


import unittest

import morphlib
from morphlib import buildenvironment


class BuildEnvironmentTests(unittest.TestCase):

    def setUp(self):
        self.settings = {
            'keep-path': False,
            'bootstrap': False,
            'toolchain-target': '%s-baserock-linux-gnu' % morphlib.util.arch(),
            'target-cflags': '',
            'prefix': '/usr',
            'no-ccache': True,
            'no-distcc': True,
            'staging-chroot': False,
        }
        self.fake_env = {
            'PATH': '/fake_bin',
        }
        self.default_path = 'no:such:path'

    def test_arch_defaults_to_host(self):
        buildenv = buildenvironment.BuildEnvironment(self.settings)
        self.assertEqual(buildenv.arch, morphlib.util.arch())

    def test_arch_overridable(self):
        buildenv = buildenvironment.BuildEnvironment(self.settings,
                                                     arch='noarch')
        self.assertEqual(buildenv.arch, 'noarch')

    def test_sets_default_path(self):
        self.settings['keep-path'] = False
        self.settings['bootstrap'] = False
        olddefaultpath = buildenvironment.BuildEnvironment._default_path
        buildenvironment.BuildEnvironment._default_path = self.default_path
        buildenv = buildenvironment.BuildEnvironment(self.settings)
        buildenvironment.BuildEnvironment._default_path = olddefaultpath
        self.assertTrue(self.default_path in buildenv.env['PATH'])

    def test_uses_env_path_with_keep_path(self):
        self.settings['keep-path'] = True

        old_osenv = buildenvironment.BuildEnvironment._osenv
        buildenvironment.BuildEnvironment._osenv = self.fake_env
        buildenv = buildenvironment.BuildEnvironment(self.settings)
        buildenvironment.BuildEnvironment._osenv = old_osenv

        self.assertEqual(buildenv.env['PATH'], self.fake_env['PATH'])

    def test_uses_env_path_with_bootstrap(self):
        self.settings['bootstrap'] = True

        old_osenv = buildenvironment.BuildEnvironment._osenv
        buildenvironment.BuildEnvironment._osenv = self.fake_env
        buildenv = buildenvironment.BuildEnvironment(self.settings)
        buildenvironment.BuildEnvironment._osenv = old_osenv

        self.assertEqual(buildenv.env['PATH'], self.fake_env['PATH'])

    def test_copies_whitelist_vars(self):
        env = self.fake_env
        safe = {
            'DISTCC_HOSTS': 'example.com:example.co.uk',
            'TMPDIR': '/buildenv/tmp/dir',
            'LD_PRELOAD': '/buildenv/lib/libbuildenv.so',
            'LD_LIBRARY_PATH': '/buildenv/lib:/buildenv/lib64',
            'FAKEROOTKEY': 'b011de73',
            'FAKED_MODE': 'non-fakeroot',
            'FAKEROOT_FD_BASE': '-1',
        }
        env.update(safe)

        old_osenv = buildenvironment.BuildEnvironment._osenv
        buildenvironment.BuildEnvironment._osenv = env
        buildenv = buildenvironment.BuildEnvironment(self.settings)
        buildenvironment.BuildEnvironment._osenv = old_osenv

        self.assertEqual(sorted(safe.items()),
                         sorted([(k, buildenv.env[k]) for k in safe.keys()]))

    def test_user_spellings_equal(self):
        buildenv = buildenvironment.BuildEnvironment(self.settings)
        self.assertTrue(buildenv.env['USER'] == buildenv.env['USERNAME'] ==
                        buildenv.env['LOGNAME'])

    def test_environment_overrides(self):
        buildenv = buildenvironment.BuildEnvironment(self.settings)
        self.assertEqual(buildenv.env['TERM'], buildenv._override_term)
        self.assertEqual(buildenv.env['SHELL'], buildenv._override_shell)
        self.assertEqual(buildenv.env['USER'], buildenv._override_username)
        self.assertEqual(buildenv.env['USERNAME'], buildenv._override_username)
        self.assertEqual(buildenv.env['LOGNAME'], buildenv._override_username)
        self.assertEqual(buildenv.env['LC_ALL'], buildenv._override_locale)
        self.assertEqual(buildenv.env['HOME'], buildenv._override_home)

    def test_environment_settings_set(self):
        buildenv = buildenvironment.BuildEnvironment(self.settings)
        self.assertEqual(buildenv.env['TOOLCHAIN_TARGET'],
                         self.settings['toolchain-target'])
        self.assertEqual(buildenv.env['CFLAGS'],
                         self.settings['target-cflags'])
        self.assertEqual(buildenv.env['PREFIX'],
                         self.settings['prefix'])
        self.assertEqual(buildenv.env['BOOTSTRAP'],
                         'true' if self.settings['bootstrap'] else 'false')

    def test_ccache_vars_set(self):
        self.settings['no-ccache'] = False
        self.settings['no-distcc'] = False
        buildenv = buildenvironment.BuildEnvironment(self.settings)
        self.assertTrue(buildenv._ccache_path in buildenv.env['PATH'])
        self.assertEqual(buildenv.env['CCACHE_PREFIX'], 'distcc')
