# Copyright (C) 2011  Codethink Limited
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License.
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


def indent(string, spaces=4):
    '''Return ``string`` indented by ``spaces`` spaces.
    
    The final line is not terminated by a newline. This makes it easy
    to use this function for indenting long text for logging: the
    logging library adds a newline, so not including it in the indented
    text avoids a spurious empty line in the log file.
    
    '''

    return '\n'.join('%*s%s' % (spaces, '', line) 
                      for line in string.splitlines())

