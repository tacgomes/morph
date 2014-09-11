# mainloop/stringbuffer.py -- efficient buffering of strings as a queue
#
# Copyright (C) 2012, 2014  Codethink Limited
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


class StringBuffer(object):

    '''Buffer data for a file descriptor.
    
    The data may arrive in small pieces, and it is buffered in a way that
    avoids excessive string catenation or splitting.
    
    '''

    def __init__(self):
        self.strings = []
        self.len = 0
        
    def add(self, data):
        '''Add data to buffer.'''
        self.strings.append(data)
        self.len += len(data)
        
    def remove(self, num_bytes):
        '''Remove specified number of bytes from buffer.'''
        while num_bytes > 0 and self.strings:
            first = self.strings[0]
            if len(first) <= num_bytes:
                num_bytes -= len(first)
                del self.strings[0]
                self.len -= len(first)
            else:
                self.strings[0] = first[num_bytes:]
                self.len -= num_bytes
                num_bytes = 0

    def peek(self):
        '''Return contents of buffer as one string.'''
        
        if len(self.strings) == 0:
            return ''
        elif len(self.strings) == 1:
            return self.strings[0]
        else:
            self.strings = [''.join(self.strings)]
            return self.strings[0]

    def read(self, max_bytes):
        '''Return up to max_bytes from the buffer.
        
        Less is returned if the buffer does not contain at least max_bytes.
        The returned data will remain in the buffer; use remove to remove
        it.
        
        '''
        
        use = []
        size = 0
        for s in self.strings:
            n = max_bytes - size
            if len(s) <= n:
                use.append(s)
                size += len(s)
            else:
                use.append(s[:n])
                size += n
                break
        return ''.join(use)

    def readline(self):
        '''Return a complete line (ends with '\n') or None.'''

        for i, s in enumerate(self.strings):
            newline = s.find('\n')
            if newline != -1:
                if newline+1 == len(s):
                    use = self.strings[:i+1]
                    del self.strings[:i+1]
                else:
                    pre = s[:newline+1]
                    use = self.strings[:i] + [pre]
                    del self.strings[:i]
                    self.strings[0] = s[newline+1:]
                return ''.join(use)
        return None
            
    def __len__(self):
        return self.len

