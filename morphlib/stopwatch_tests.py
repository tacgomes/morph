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
        assert self.stopwatch.times('tick')
        assert self.stopwatch.time('tick', 'a')
        assert self.stopwatch.times('tick').has_key('a')
        assert (self.stopwatch.time('tick', 'a') ==
                self.stopwatch.times('tick')['a'])
        
        now = datetime.datetime.now()
        assert self.stopwatch.time('tick', 'a') < now

    def test_start_stop(self):
        self.stopwatch.start('start-stop')
        assert self.stopwatch.times('start-stop')
        assert self.stopwatch.start_time('start-stop')

        self.stopwatch.stop('start-stop')
        assert self.stopwatch.times('start-stop')
        assert self.stopwatch.stop_time('start-stop')

        start = self.stopwatch.start_time('start-stop')
        stop = self.stopwatch.stop_time('start-stop')

        our_delta = stop - start
        watch_delta = self.stopwatch.start_stop_delta('start-stop')

        assert our_delta.total_seconds() > 0
        assert our_delta == watch_delta
