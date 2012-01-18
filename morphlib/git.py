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


import logging
import urlparse
import binascii
import morphlib


class NoMorphs(Exception):

    def __init__(self, repo, ref):
        Exception.__init__(self, 
                            'Cannot find any morpologies at %s:%s' %
                                (repo, ref))


class TooManyMorphs(Exception):

    def __init__(self, repo, ref, morphs):
        Exception.__init__(self, 
                            'Too many morphologies at %s:%s: %s' %
                                (repo, ref, ', '.join(morphs)))

class InvalidTreeish(Exception):

    def __init__(self, repo, ref):
        Exception.__init__(self, 
                            '%s is an invalid reference for repo %s' %
                                (ref,repo))


class Treeish:
    def __init__(self, repo, ref):
        self.repo = repo
        self.sha1 = None
        self.ref = None
        self._resolve_ref(ref) 
        
    def _resolve_ref(self, ref):
        ex = morphlib.execute.Execute(self.repo, msg=logging.debug)
        try:
            refs = ex.runv(['git', 'show-ref', ref]).split()
            binascii.unhexlify(refs[0]) #Valid hex?
            self.sha1 = refs[0]
            self.ref = refs[1]
        except morphlib.execute.CommandFailure:
            self._is_treeish(ref)

    def _is_treeish(self, ref):
        try:
            if len(ref)==40:
                binascii.unhexlify(ref)	
                ex = morphlib.execute.Execute(self.repo, msg=logging.debug)
                try:
                    refs = ex.runv(['git', 'rev-list', '--no-walk', ref])
                    self.sha1=REF
                except morphlib.execute.CommandFailure:
                    raise InvalidTreeish(self.repo,ref)

        except TypeError:
            raise InvalidTreeish(self.repo,ref)

def export_sources(treeish, tar_filename):
    '''Export the contents of a specific commit into a compressed tarball.'''
    ex = morphlib.execute.Execute('.', msg=logging.debug)
    ex.runv(['git', 'archive', '-o', tar_filename, '--remote', treeish.repo, treeish.sha1])

def get_morph_text(treeish, filename):
    '''Return a morphology from a git repository.'''
    ex = morphlib.execute.Execute(treeish.repo, msg=logging.debug)
    return ex.runv(['git', 'cat-file', 'blob', '%s:%s' % (treeish.sha1, filename)])

def extract_bundle(location, bundle):
    '''Extract a bundle into git at location'''
    ex = morphlib.execute.Execute(location, msg=logging.debug)
    return ex.runv(['git', 'bundle', 'unbundle', bundle])

def clone(location, repo):
    '''clone at git repo into location'''
    ex = morphlib.execute.Execute('.', msg=logging.debug)
    return ex.runv(['git', 'clone', repo, location])

