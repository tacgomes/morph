# distbuild/idgen.py -- generate unique identifiers
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


class IdentifierGenerator(object):

    '''Generate unique identifiers.'''

    def __init__(self, series):
        self._series = series
        self._counter = 0
        
    def next(self):
        self._counter += 1
        return '%s-%d' % (self._series, self._counter)

