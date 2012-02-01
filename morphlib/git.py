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


import logging
import binascii
import morphlib
import os
import cliapp


class NoMorphs(Exception):

    def __init__(self, repo, ref):
        Exception.__init__(self, 'Cannot find any morpologies at %s:%s' %
                           (repo, ref))


class TooManyMorphs(Exception):

    def __init__(self, repo, ref, morphs):
        Exception.__init__(self, 'Too many morphologies at %s:%s: %s' %
                           (repo, ref, ', '.join(morphs)))


class InvalidTreeish(cliapp.AppException):

    def __init__(self, repo, ref):
        Exception.__init__(self, '%s is an invalid reference for repo %s' %
                           (ref, repo))


class Treeish(object):

    def __init__(self, repo, original_repo, ref, msg=logging.debug):
        self.repo = repo
        self.msg = msg
        self.sha1 = None
        self.ref = None
        self.original_repo = original_repo
        self._resolve_ref(ref) 

    def __hash__(self):
        return hash((self.repo, self.ref))

    def __eq__(self, other):
        return other.repo == self.repo and other.ref == self.ref

    def __str__(self):
        return '%s:%s' % (self.repo, self.ref)

    def _resolve_ref(self, ref):
        ex = morphlib.execute.Execute(self.repo, self.msg)
        try:
            refs = ex.runv(['git', 'show-ref', ref]).split('\n')

            # drop the refs that are not from origin
            refs = [x.split() for x in refs if 'origin' in x]

            binascii.unhexlify(refs[0][0]) #Valid hex?
            self.sha1 = refs[0][0]
            self.ref = refs[0][1]
        except morphlib.execute.CommandFailure:
            self._is_sha(ref)

    def _is_sha(self, ref):
        if len(ref) != 40:
            raise InvalidTreeish(self.original_repo, ref)

        try:
                binascii.unhexlify(ref)
                ex = morphlib.execute.Execute(self.repo, self.msg)
                ex.runv(['git', 'rev-list', '--no-walk', ref])
                self.sha1=ref
        except (TypeError, morphlib.execute.CommandFailure):
            raise InvalidTreeish(self.original_repo, ref)

def export_sources(treeish, tar_filename):
    '''Export the contents of a specific commit into a compressed tarball.'''
    ex = morphlib.execute.Execute('.', msg=logging.debug)
    ex.runv(['git', 'archive', '-o', tar_filename, '--remote',
             'file://%s' % treeish.repo, treeish.sha1])

def get_morph_text(treeish, filename, msg=logging.debug):
    '''Return a morphology from a git repository.'''
    ex = morphlib.execute.Execute(treeish.repo, msg=msg)
    return ex.runv(['git', 'cat-file', 'blob', '%s:%s'
                   % (treeish.sha1, filename)])

def extract_bundle(location, bundle, msg=logging.debug):
    '''Extract a bundle into git at location'''
    ex = morphlib.execute.Execute(location, msg=msg)
    return ex.runv(['git', 'bundle', 'unbundle', bundle])

def clone(location, repo, msg=logging.debug):
    '''clone at git repo into location'''
    ex = morphlib.execute.Execute('.', msg=msg)
    return ex.runv(['git', 'clone', '-l', repo, location])

def init(location, msg=logging.debug):
    '''initialise git repo at location'''
    os.mkdir(location)
    ex = morphlib.execute.Execute(location, msg=msg)
    return ex.runv(['git', 'init'])

def add_remote(gitdir, name, url, msg=logging.debug):
    '''add remote with name 'name' for url at gitdir'''
    ex = morphlib.execute.Execute(gitdir, msg=msg)
    return ex.runv(['git', 'remote', 'add', '-f', name, url])

def update_remote(gitdir, name, msg=logging.debug):
    ex = morphlib.execute.Execute(gitdir, msg=msg)
    return ex.runv(['git', 'remote', 'update', name])
