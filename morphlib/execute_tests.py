# Copyright (C) 2011  Codethink Limited
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
import unittest

import morphlib


class ExecuteTests(unittest.TestCase):

    def setUp(self):
        self.e = morphlib.execute.Execute('/', lambda msg: None)

    def test_has_same_path_as_environment(self):
        self.assertEqual(self.e.env['PATH'], os.environ['PATH'])

    def test_executes_true_ok(self):
        self.assertEqual(self.e.run(['true']), [''])

    def test_raises_commandfailure_for_false(self):
        self.assertRaises(morphlib.execute.CommandFailure,
                          self.e.run, ['false'])

    def test_run_commandfailure_contains_both_stdout_and_stderr_output(self):
        try:
            self.e.run(['printf "%s%s\n" foo msg; '
                        'printf "%s%s" bar msg 1>&2; '
                        'exit 1'])
        except morphlib.execute.CommandFailure, e:
            self.assert_('foomsg' in str(e))
            self.assert_('barmsg' in str(e))
        else:
            self.assertTrue(False)

    def test_returns_stdout_from_all_commands(self):
        self.assertEqual(self.e.run(['echo foo', 'echo bar']),
                         ['foo\n', 'bar\n'])

    def test_sets_working_directory(self):
        self.assertEqual(self.e.run(['pwd']), ['/\n'])

    def test_executes_argv(self):
        self.assertEqual(self.e.runv(['echo', 'foo']), 'foo\n')

    def test_raises_error_when_argv_fails(self):
        self.assertRaises(morphlib.execute.CommandFailure,
                          self.e.runv, ['false'])

    def test_runv_commandfailure_contains_both_stdout_and_stderr_output(self):
        try:
            self.e.runv(['sh', '-c', 
                         'printf "%s%s\n" foo msg; '
                         'printf "%s%s" bar msg 1>&2; '
                         'exit 1'])
        except morphlib.execute.CommandFailure, e:
            self.assert_('foomsg' in str(e))
            self.assert_('barmsg' in str(e))
        else:
            self.assertTrue(False)

    def test_runv_sets_working_directory(self):
        self.assertEqual(self.e.runv(['pwd']), '/\n')

    def test_runs_as_fakeroot_when_requested(self):
        self.assertEqual(self.e.run(['id -u'], as_fakeroot=True), ['0\n'])

    def test_runvs_as_fakeroot_when_requested(self):
        self.assertEqual(self.e.runv(['id', '-u'], as_fakeroot=True), '0\n')

