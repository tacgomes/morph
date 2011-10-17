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


'''Functions for dealing with Baserock binaries.

Binaries are chunks, strata, and system images.

'''


import logging
import tarfile

import morphlib


def create_chunk(rootdir, chunk_filename):
    '''Create a chunk from the contents of a directory.'''
    logging.debug('Creating chunk file %s from %s' % (chunk_filename, rootdir))
    tar = tarfile.open(name=chunk_filename, mode='w:gz')
    tar.add(rootdir, arcname='.')
    tar.close()


def unpack_chunk(chunk_filename, dirname):
    '''Unpack a chunk into a directory.
    
    The directory must exist already.
    
    '''

    logging.debug('Unpacking chunk %s into %s' % (chunk_filename, dirname))
    tar = tarfile.open(name=chunk_filename)
    tar.extractall(path=dirname)
    tar.close()


def create_stratum(rootdir, stratum_filename):
    '''Create a stratum from the contents of a directory.'''
    logging.debug('Creating stratum file %s from %s' % 
                    (stratum_filename, rootdir))
    tar = tarfile.open(name=stratum_filename, mode='w:gz')
    tar.add(rootdir, arcname='.')
    tar.close()


def unpack_stratum(stratum_filename, dirname):
    '''Unpack a stratum into a directory.
    
    The directory must exist already.
    
    '''

    logging.debug('Unpacking stratum %s into %s' % (stratum_filename, dirname))
    tar = tarfile.open(name=stratum_filename)
    tar.extractall(path=dirname)
    tar.close()

