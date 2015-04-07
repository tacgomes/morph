# distbuild/subprocess_eventsrc.py -- for managing subprocesses
#
# Copyright (C) 2014-2015  Codethink Limited
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
# with this program.  If not, see <http://www.gnu.org/licenses/>.


import logging
import os
import signal

import distbuild


class FileReadable(object):

    def __init__(self, request_id, p, f):
        self.request_id = request_id
        self.process = p
        self.file = f


class FileWriteable(object):

    def __init__(self, request_id, p, f):
        self.request_id = request_id
        self.process = p
        self.file = f


class SubprocessEventSource(distbuild.EventSource):
    '''Event source for monitoring one or more subprocesses.

    This will send FileReadable and FileWritable events based on the
    stdin and stdout and stderr handles of each subprocesses.

    When the subprocess terminates, you'll receive final FileReadable events
    for stdout and for stderr. At that point, reading from those file
    descriptors will return None, at which point you can be sure that the
    subprocess is no longer running.

    '''

    def __init__(self):
        self.procs = []
        self.closed = False

    def get_select_params(self):
        r = []
        w = []
        for requst_id, p in self.procs:
            if p.stdin_contents is not None:
                w.append(p.stdin)
            if p.stdout is not None:
                r.append(p.stdout)
            if p.stderr is not None:
                r.append(p.stderr)
        return r, w, [], None

    def get_events(self, r, w, x):
        events = []

        for request_id, p in self.procs:
            if p.stdin in w:
                events.append(FileWriteable(request_id, p, p.stdin))
            if p.stdout in r:
                events.append(FileReadable(request_id, p, p.stdout))
            if p.stderr in r:
                events.append(FileReadable(request_id, p, p.stderr))

        return events

    def add(self, request_id, process):

        self.procs.append((request_id, process))
        distbuild.set_nonblocking(process.stdin)
        distbuild.set_nonblocking(process.stdout)
        distbuild.set_nonblocking(process.stderr)

    def remove(self, process):
        self.procs = [t for t in self.procs if t[1] != process]

    def kill_by_id(self, request_id):
        logging.debug('SES: Killing all processes for %s', request_id)
        for id, process in self.procs:
            if id == request_id:
                logging.debug('SES: killing process group of %r', process)
                os.killpg(process.pid, signal.SIGKILL)

    def close(self):
        self.procs = []
        self.closed = True

    def is_finished(self):
        return self.closed
