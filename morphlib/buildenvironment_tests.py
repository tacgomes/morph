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
        self.target = '%s-baserock-linux-gnu' % morphlib.util.arch()
        self.fake_env = {
            'PATH': '/fake_bin',
        }

    def new_build_env(self, settings=None, target=None, **kws):
        settings = settings or self.settings
        target = target or self.target
        return buildenvironment.BuildEnvironment(settings, target, **kws)

    def new_build_env(self, settings=None, target=None, **kws):
        settings = settings or self.settings
        target = target or self.target
        return buildenvironment.BuildEnvironment(settings, target, **kws)

    def test_arch_defaults_to_host(self):
        buildenv = self.new_build_env()
        self.assertEqual(buildenv.arch, morphlib.util.arch())

    def test_arch_overridable(self):
        buildenv = self.new_build_env(arch='noarch')
        self.assertEqual(buildenv.arch, 'noarch')

    def test_target_always_valid(self):
        self.assertRaises(morphlib.Error, self.new_build_env, target="invalid")

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

    def test_environment_settings_set(self):
        buildenv = self.new_build_env()
        self.assertEqual(buildenv.env['TARGET'], self.target)

    def test_ccache_vars_set(self):
        new_settings = copy.copy(self.settings)
        new_settings['no-ccache'] = False
        new_settings['no-distcc'] = False
        buildenv = self.new_build_env(settings=new_settings)
        self.assertTrue(buildenv._ccache_path in buildenv.extra_path)
        self.assertEqual(buildenv.env['CCACHE_PREFIX'], 'distcc')
