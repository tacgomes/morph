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
import os
import re
import tarfile

import morphlib


def create_chunk(rootdir, chunk_filename, regexps, dump_memory_profile=None):
    '''Create a chunk from the contents of a directory.
    
    Only files and directories that match at least one of the regular
    expressions are accepted. The regular expressions are implicitly
    anchored to the beginning of the string, but not the end. The 
    filenames are relative to rootdir.
    
    '''

    dump_memory_profile = dump_memory_profile or (lambda msg: None )
       
    def mkrel(filename):
        assert filename.startswith(rootdir)
        if filename == rootdir:
            return '.'
        assert filename.startswith(rootdir + '/')
        return filename[len(rootdir + '/'):]

    def matches(filename):
        return any(x.match(filename) for x in compiled)

    def names_to_root(filename):
        yield filename
        while filename != rootdir:
            filename = os.path.dirname(filename)
            yield filename

    logging.debug('Creating chunk file %s from %s with regexps %s' % 
                    (chunk_filename, rootdir, regexps))
    dump_memory_profile('at beginning of create_chunk')

    compiled = [re.compile(x) for x in regexps]
    include = set()
    for dirname, subdirs, basenames in os.walk(rootdir):
        if matches(dirname):
            include.add(dirname)
        subdirpaths = [os.path.join(dirname, x) for x in subdirs]
        subdirsymlinks = [x for x in subdirpaths if os.path.islink(x)]
        filenames = [os.path.join(dirname, x) for x in basenames]
        for filename in subdirsymlinks + filenames:
            if matches(mkrel(filename)):
                for name in names_to_root(filename):
                    if name not in include:
                        logging.debug('regexp match: %s' % name)
                        include.add(name)
            else:
                logging.debug('regexp MISMATCH: %s' % filename)
    dump_memory_profile('after walking')

    include = sorted(include)

    tar = tarfile.open(name=chunk_filename, mode='w:gz')
    for filename in include:
        tar.add(filename, arcname=mkrel(filename), recursive=False)
    tar.close()
    dump_memory_profile('after creating tarball')

    include.remove(rootdir)
    for filename in reversed(include):
        if os.path.isdir(filename) and not os.path.islink(filename):
            if not os.listdir(filename):
                os.rmdir(filename)
        else:
            os.remove(filename)
    dump_memory_profile('after removing in create_chunks')


def create_stratum(rootdir, stratum_filename):
    '''Create a stratum from the contents of a directory.'''
    logging.debug('Creating stratum file %s from %s' % 
                    (stratum_filename, rootdir))
    tar = tarfile.open(name=stratum_filename, mode='w:gz')
    tar.add(rootdir, arcname='.')
    tar.close()


def unpack_binary(filename, dirname):
    '''Unpack a binary into a directory.
    
    The directory must exist already.
    
    '''

    logging.debug('Unpacking %s into %s' % (filename, dirname))
    ex = morphlib.execute.Execute(dirname, msg=lambda s: None)
    ex.runv(['tar', '-xvf', filename])

