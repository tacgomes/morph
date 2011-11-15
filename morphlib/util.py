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


'''Utility functions for morph.'''


try:
     from multiprocessing import cpu_count
except NotImplementedError:
    cpu_count = lambda: 1
import os


def arch():
    '''Return the CPU architecture of the current host.'''
    return os.uname()[4]



def indent(string, spaces=4):
    '''Return ``string`` indented by ``spaces`` spaces.
    
    The final line is not terminated by a newline. This makes it easy
    to use this function for indenting long text for logging: the
    logging library adds a newline, so not including it in the indented
    text avoids a spurious empty line in the log file.
    
    This also makes the result be a plain ASCII encoded string.
    
    '''

    if type(string) == unicode: # pragma: no cover
        string = string.decode('utf-8')
    lines = string.splitlines()
    lines = ['%*s%s' % (spaces, '', line) for line in lines]
    return '\n'.join(lines)



def make_concurrency(cores=None):
    '''Return the number of concurrent jobs for make.
    
    This will be given to make as the -j argument.

    '''

    n = multiprocessing.cpu_count() if cores is None else cores
    # Experimental results (ref. Kinnison) says a factor of 1.5
    # gives about the optimal result for build times, since much of
    # builds are I/O bound, not CPU bound.
    return max(int(n * 1.5 + 0.5), 1)

