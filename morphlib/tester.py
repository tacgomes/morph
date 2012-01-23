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


import imp
import os
import re
import select
import subprocess
import sys
import time


class Timeout(Exception):

    def __str__(self):
        buf, regexp = self.args
        return 'Cannot find %s in %s' % (repr(regexp), repr(buf))


class System(object):

    '''Abstract interface to a system.
    
    The interface allows starting and stopping the system, and interacting
    with its via a serial console.
    
    '''

    def start(self):
        '''Start the system.'''
        raise NotImplementedError()

    def stop(self):
        '''Stop the system.'''
        raise NotImplementedError()

    def waitfor(self, regexp, timeout):
        '''Wait system to output a match for ``regexp`` on the serial console.
        
        If timeout is exceeded, raise Timeout.
        
        '''
        raise NotImplementedError()

    def send(self, text):
        '''Send TEXT via the serial console to the system.'''
        raise NotImplementedError()


class KvmSystem(System):

    '''A system running under KVM.'''

    def __init__(self, image_filename, verbose=False, timeout=None):
        self.image_filename = image_filename
        self.verbose = verbose
        self.timeout = timeout
        self.p = None
        self.stdin_buf = ''
        self.stdout_buf = ''
        
    def start(self):
        self.p = subprocess.Popen(['kvm', '-nographic', self.image_filename],
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)

    def stop(self):
        self.p.terminate()
        self.p.wait()

    def _io(self, timeout):
        r, w, x = select.select([self.p.stdout], [self.p.stdin], [], timeout)
        if self.p.stdout in r:
            byte = self.p.stdout.read(1)
            if byte:
                if self.verbose:
                    sys.stdout.write(byte)
                    sys.stdout.flush()
                self.stdout_buf += byte
        elif self.p.stdin in w:
            if self.stdin_buf:
                byte = self.stdin_buf[0]
                self.p.stdin.write(byte)
                self.p.stdin.flush()
                self.stdin_buf = self.stdin_buf[1:]
        else:
            if self.verbose:
                sys.stdout.write('_')
                sys.stdout.flush()

    def waitfor(self, regexp, timeout=None):
        pat = re.compile(regexp, re.DOTALL | re.MULTILINE)
        started = time.time()
        timeout = timeout if timeout is not None else self.timeout
        remaining = timeout
        while not pat.search(self.stdout_buf) and remaining > 0:
            self._io(remaining)
            remaining = (started + timeout) - time.time()
        m = pat.search(self.stdout_buf)
        if not m:
            raise Timeout(self.stdout_buf, regexp)
        self.stdout_buf = self.stdout_buf[m.end():]

    def send(self, text):
        self.stdin_buf += text


class TestStory(object):

    '''Execute a test story.'''
    
    def __init__(self, system, steps, msg):
        self.system = system
        self.steps = steps
        self.msg = msg
        
    def run(self):
        self.system.start()
        for t in self.steps:
            if len(t) == 2:
                send, expect = t
                timeout = None
            else:
                assert len(t) == 3
                send, expect, timeout = t
            self.msg('Sending: %s' % repr(send))
            self.msg('Expecting: %s' % repr(expect))
            self.system.send(send)
            self.system.waitfor(expect, timeout=timeout)
        self.system.stop()


def load_module(filename):
    for t in imp.get_suffixes():
        suffix, mode, kind = t
        if filename.endswith(suffix):
            module_name = os.path.basename(filename[:-len(suffix)])
            with open(filename, mode) as f:
                return imp.load_module(module_name, f, filename, t)
    raise Exception("Unknown module: %s" % filename)

