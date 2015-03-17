# mainloop/socketsrc.py -- events and event sources for sockets
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


import fcntl
import logging
import os
import socket

import distbuild

from eventsrc import EventSource


def set_nonblocking(handle):
    '''Make a socket, file descriptor, or other such thing be non-blocking.'''

    if type(handle) is int:
        fd = handle
    else:
        fd = handle.fileno()

    flags = fcntl.fcntl(fd, fcntl.F_GETFL, 0)
    flags = flags | os.O_NONBLOCK
    fcntl.fcntl(fd, fcntl.F_SETFL, flags)


class SocketError(object):

    '''An error has occured with a socket.'''

    def __init__(self, sock, exception):
        self.sock = sock
        self.exception = exception


class NewConnection(object):

    '''A new client connection.'''

    def __init__(self, connection, addr):
        self.connection = connection
        self.addr = addr
        

class ListeningSocketEventSource(EventSource):

    '''An event source for a socket that listens for connections.'''

    def __init__(self, addr, port):
        self.sock = distbuild.create_socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        logging.info('Binding socket to %s', addr)
        self.sock.bind((addr, port))
        self.sock.listen(5)
        self._accepting = True
        logging.info('Listening at %s' % self.sock.remotename())

    def get_select_params(self):
        r = [self.sock.fileno()] if self._accepting else []
        return r, [], [], None

    def get_events(self, r, w, x):
        if self._accepting and self.sock.fileno() in r:
            try:
                conn, addr = self.sock.accept()
            except socket.error as e:
                return [SocketError(self.sock, e)]
            else:
                logging.info(
                    'New connection to %s from %s' %
                        (conn.getsockname(), addr))
                return [NewConnection(conn, addr)]
            
        return []

    def start_accepting(self):
        self._accepting = True
        
    def stop_accepting(self):
        self._accepting = False


class SocketReadable(object):

    '''A socket is readable.'''

    def __init__(self, sock):
        self.sock = sock


class SocketWriteable(object):

    '''A socket is writeable.'''

    def __init__(self, sock):
        self.sock = sock


class SocketEventSource(EventSource):

    '''Event source for normal sockets (for I/O).
    
    This generates events for indicating the socket is readable or
    writeable. It does not actually do any I/O itself, that's for the
    handler of the events. There are, however, methods for doing the
    reading/writing, and for closing the socket.
    
    The event source can be told to stop checking for readability
    or writeability, so that the user may, for example, stop those
    events from being triggered while a buffer is full.
    
    '''

    def __init__(self, sock):
        self.sock = sock
        self._reading = True
        self._writing = True

        set_nonblocking(sock)

    def __repr__(self):
        return '<SocketEventSource at %x: socket %s>' % (id(self), self.sock)

    def get_select_params(self):
        r = [self.sock.fileno()] if self._reading else []
        w = [self.sock.fileno()] if self._writing else []
        return r, w, [], None

    def get_events(self, r, w, x):
        events = []
        fd = self.sock.fileno()

        if self._reading and fd in r:
            events.append(SocketReadable(self))

        if self._writing and fd in w:
            events.append(SocketWriteable(self))
            
        return events

    def start_reading(self):
        self._reading = True
        
    def stop_reading(self):
        self._reading = False

    def start_writing(self):
        self._writing = True
        
    def stop_writing(self):
        self._writing = False

    def read(self, max_bytes):
        fd = self.sock.fileno()
        return os.read(fd, max_bytes)
        
    def write(self, data):
        fd = self.sock.fileno()
        return os.write(fd, data)

    def close(self):
        self.stop_reading()
        self.stop_writing()
        self.sock.close()
        self.sock = None
        
    def is_finished(self):
        return self.sock is None

