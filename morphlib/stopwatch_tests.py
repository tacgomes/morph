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


import datetime
import unittest

import morphlib


class StopwatchTests(unittest.TestCase):

    def setUp(self):
        self.stopwatch = morphlib.stopwatch.Stopwatch()
        
    def tearDown(self):
        pass

    def test_tick(self):
        self.stopwatch.tick('tick', 'a')
        self.assertTrue(self.stopwatch.times('tick'))
        self.assertTrue(self.stopwatch.time('tick', 'a'))
        self.assertIn('a', self.stopwatch.times('tick'))
        self.assertEqual(self.stopwatch.time('tick', 'a'),
            self.stopwatch.times('tick')['a'])
        
        now = datetime.datetime.now()
        self.assertTrue(self.stopwatch.time('tick', 'a') < now)

    def test_start_stop(self):
        self.stopwatch.start('start-stop')
        self.assertTrue(self.stopwatch.times('start-stop'))
        self.assertTrue(self.stopwatch.start_time('start-stop'))

        self.stopwatch.stop('start-stop')
        self.assertTrue(self.stopwatch.times('start-stop'))
        self.assertTrue(self.stopwatch.stop_time('start-stop'))

        start = self.stopwatch.start_time('start-stop')
        stop = self.stopwatch.stop_time('start-stop')

        our_delta = stop - start
        watch_delta = self.stopwatch.start_stop_delta('start-stop')
        self.assertEqual(our_delta, watch_delta)

        self.assertTrue(self.stopwatch.start_stop_seconds('start-stop') > 0)
        
    def test_with(self):
        with self.stopwatch('foo'):
            pass
        self.assert_(self.stopwatch.start_stop_seconds('foo') < 1.0)
        
    def test_with_within_with(self):
        with self.stopwatch('foo'):
            with self.stopwatch('bar'):
                pass
        self.assert_(self.stopwatch.start_time('foo'))
        self.assert_(self.stopwatch.stop_time('foo'))
        self.assert_(self.stopwatch.start_time('bar'))
        self.assert_(self.stopwatch.stop_time('bar'))
        self.assert_(self.stopwatch.start_stop_seconds('foo') < 1.0)
        self.assert_(self.stopwatch.start_stop_seconds('bar') < 1.0)

