# Copyright (C) 2011-2012  Codethink Limited
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


import operator
import datetime


class Stopwatch(object):

    def __init__(self):
        self.ticks = {}
        self.context_stack = []

    def tick(self, reference_object, name):
        if not reference_object in self.ticks:
            self.ticks[reference_object] = {}
        self.ticks[reference_object][name] = datetime.datetime.now()

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

    def start_stop_seconds(self, reference_object):
        delta = self.start_stop_delta(reference_object)
        return (delta.days * 24 * 3600 +
                delta.seconds +
                operator.truediv(delta.microseconds, 10**6))

    def __call__(self, reference_object):
        self.context_stack.append(reference_object)
        return self
                
    def __enter__(self):
        self.start(self.context_stack[-1])
        return self
        
    def __exit__(self, *args):
        self.stop(self.context_stack[-1])
        self.context_stack.pop()
        return False # cause any exception to be re-raised

