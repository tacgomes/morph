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
from morphlib import buildworker


class DummyApp(object):

    def __init__(self):
        self.settings = {}
        self.msg = lambda x: '%s' % x


class BuildWorkerTests(unittest.TestCase):

    def test_construction_with_name_ident_and_app(self):
        app = DummyApp()
        worker = buildworker.BuildWorker('local-1', 'local', app)
        
        self.assertEqual(worker.name, 'local-1')
        self.assertEqual(worker.ident, 'local')
        self.assertEqual(worker.settings, app.settings)

    def test_methods_that_need_to_be_overloaded(self):
        app = DummyApp()
        worker = buildworker.BuildWorker('local-1', 'local', app)
        self.assertRaises(NotImplementedError, worker.build, [])

    def test_conversion_to_a_string(self):
        app = DummyApp()
        worker = buildworker.BuildWorker('local-1', 'local', app)
        self.assertEquals(str(worker), 'local-1')

    def test_local_builder_construction_with_name_ident_and_app(self):
        app = DummyApp()
        worker = buildworker.LocalBuildWorker('local-1', 'local', app)
        
        self.assertEqual(worker.name, 'local-1')
        self.assertEqual(worker.ident, 'local')
        self.assertEqual(worker.settings, app.settings)

    def test_remote_builder_construction_with_name_ident_and_app(self):
        app = DummyApp()
        worker = buildworker.RemoteBuildWorker('user@host-1', 'user@host', app)
        
        self.assertEqual(worker.name, 'user@host-1')
        self.assertEqual(worker.ident, 'user@host')
        self.assertEqual(worker.hostname, 'user@host')
        self.assertEqual(worker.settings, app.settings)
