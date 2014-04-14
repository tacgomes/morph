# distbuild/distbuild_socket.py -- wrapper around Python 'socket' module.
#
# Copyright (C) 2014  Codethink Limited
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
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA..


import socket


class DistbuildSocket(object):
    '''Wraps socket.SocketType with a few helper functions.'''

    def __init__(self, real_socket):
        self.real_socket = real_socket

    def __getattr__(self, name):
        return getattr(self.real_socket, name)

    def __repr__(self):
        return '<DistbuildSocket at 0x%x: %s>' % (id(self), str(self))

    def __str__(self):
        localname = self.localname() or '(closed)'
        remotename = self.remotename()
        if remotename is None:
            return '%s' % self.localname()
        else:
            return '%s -> %s' % (self.localname(), remotename)

    def accept(self, *args):
        result = self.real_socket.accept(*args)
        return DistbuildSocket(result[0]), result[1:]

    def localname(self):
        '''Get local end of socket connection as a string.'''
        try:
            return '%s:%s' % self.getsockname()
        except socket.error:
            # If the socket is in destruction we may get EBADF here.
            return None

    def remotename(self):
        '''Get remote end of socket connection as a string.'''
        try:
            return '%s:%s' % self.getpeername()
        except socket.error:
            return None


def create_socket(*args):
    return DistbuildSocket(socket.socket(*args))
