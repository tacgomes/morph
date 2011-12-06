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


from datetime import datetime


class Stopwatch(object):

    def __init__(self):
        self.ticks = {}

    def tick(self, reference_object, name):
        if not self.ticks.has_key(reference_object):
            self.ticks[reference_object] = {}
        self.ticks[reference_object][name] = datetime.now()

    def start(self, reference_object):
        self.tick(reference_object, 'start')

    def stop(self, reference_object):
        self.tick(reference_object, 'stop')

    def times(self, reference_object):
        return self.ticks[reference_object]

    def time(self, reference_object, name):
        return self.ticks[reference_object][name]

    def start_time(self, reference_object):
        return self.ticks[reference_object]['start']

    def stop_time(self, reference_object):
        return self.ticks[reference_object]['stop']

    def start_stop_delta(self, reference_object):
        return (self.stop_time(reference_object) - 
                self.start_time(reference_object))
