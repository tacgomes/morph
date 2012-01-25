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


class DummyApp(object):

    def __init__(self):
        self.settings = {}
        self.msg = lambda x: '%s' % x


class DummyWorker(object):

    def __init__(self, name, ident):
        self.name = name
        self.ident = ident


class BuildControllerTests(unittest.TestCase):

    def test_construction_with_app_and_tempdir(self):
        app = DummyApp()
        tempdir = '/foo/bar'
        controller = morphlib.buildcontroller.BuildController(app, tempdir)
        self.assertEqual(app.settings, controller.settings)
        self.assertEqual(tempdir, controller.tempdir)

    def test_adding_workers(self):
        app = DummyApp()
        tempdir = '/foo/bar'
        controller = morphlib.buildcontroller.BuildController(app, tempdir)

        worker1 = object()
        worker2 = object()
        worker3 = object()

        controller.add_worker(worker1)
        self.assertTrue(worker1 in controller.workers)
        self.assertTrue(worker2 not in controller.workers)
        self.assertTrue(worker3 not in controller.workers)

        controller.add_worker(worker2)
        self.assertTrue(worker1 in controller.workers)
        self.assertTrue(worker2 in controller.workers)
        self.assertTrue(worker3 not in controller.workers)

        controller.add_worker(worker3)
        self.assertTrue(worker1 in controller.workers)
        self.assertTrue(worker2 in controller.workers)
        self.assertTrue(worker3 in controller.workers)

    def test_generation_of_worker_names(self):
        app = DummyApp()
        tempdir = '/foo/bar'
        controller = morphlib.buildcontroller.BuildController(app, tempdir)
        
        localname1 = controller.generate_worker_name('local')
        worker1 = DummyWorker(localname1, 'local')
        controller.add_worker(worker1)
        localname2 = controller.generate_worker_name('local')
        worker2 = DummyWorker(localname1, 'local')
        controller.add_worker(worker2)
        localname3 = controller.generate_worker_name('local')
        worker3 = DummyWorker(localname1, 'local')
        controller.add_worker(worker3)

        self.assertEqual(localname1, 'local-1')
        self.assertEqual(localname2, 'local-2')
        self.assertEqual(localname3, 'local-3')
