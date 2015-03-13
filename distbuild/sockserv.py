# mainloop/sockserv.py -- socket server state machines
#
# Copyright (C) 2012, 2014-2015  Codethink Limited
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

from sm import StateMachine
from socketsrc import NewConnection, SocketError, ListeningSocketEventSource


class ListenServer(StateMachine):

    '''Listen for new connections on a port, send events for them.'''

    def __init__(self, addr, port, machine, extra_args=None, port_file=''):
        StateMachine.__init__(self, 'listening')
        self._addr = addr
        self._port = port
        self._machine = machine
        self._extra_args = extra_args or []
        self._port_file = port_file
        
    def setup(self):
        src = ListeningSocketEventSource(self._addr, self._port)
        if self._port_file:
            host, port = src.sock.getsockname()
            with open(self._port_file, 'w') as f:
                f.write('%s\n' % port)
        self.mainloop.add_event_source(src)

        spec = [
            # state, source, event_class, new_state, callback
            ('listening', src, NewConnection, 'listening', self.new_conn),
            ('listening', src, SocketError, None, self.report_error),
        ]
        self.add_transitions(spec)

    def new_conn(self, event_source, event):
        logging.debug(
            'ListenServer: Creating new %s using %s and %s' %
                (self._machine,
                 repr(event.connection),
                 repr(self._extra_args)))
        m = self._machine(event.connection, *self._extra_args)
        self.mainloop.add_state_machine(m)

    def report_error(self, event_source, event):
        logging.error(str(event))

