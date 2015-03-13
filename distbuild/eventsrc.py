# mainloop/eventsrc.py -- interface for event sources
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


class EventSource(object):

    '''A source of events for state machines.
    
    This is a base class.
    
    An event source watches one file descriptor, and returns events
    related to it. The events may vary depending on the file descriptor.
    The actual watching is done using select.select.
    
    '''
    
    def get_select_params(self):
        '''Return parameters to use for select for this event source.
        
        Three lists of file descriptors, and a timeout are returned.
        The three lists and the timeout are used as arguments to the 
        select.select function, though they may be manipulated and
        combined with return values from other event sources.
        
        '''
        
        return [], [], [], None

    def get_events(self, r, w, x):
        '''Return events related to this file descriptor.
        
        The arguments are the return values of select.select.
        
        '''
        
        return []

    def is_finished(self):
        '''Is this event source finished?
        
        It's finished if it won't ever return any new events.
        
        '''
        
        return False

