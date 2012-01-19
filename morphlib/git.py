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
import urlparse
import binascii
import morphlib
import os
import cliapp


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

class InvalidTreeish(cliapp.AppException):

    def __init__(self, repo, ref):
        Exception.__init__(self, 
                            '%s is an invalid reference for repo %s' %
                                (ref,repo))


class Treeish:
    def __init__(self, repo, ref, msg=logging.debug):
        self.repo = repo
        self.msg = msg
        self.sha1 = None
        self.ref = None
        self._resolve_ref(ref) 
        
    def _resolve_ref(self, ref):
        ex = morphlib.execute.Execute(self.repo, self.msg)
        try:
            refs = ex.runv(['git', 'show-ref', ref]).split()
            binascii.unhexlify(refs[0]) #Valid hex?
            self.sha1 = refs[0]
            self.ref = refs[1]
        except morphlib.execute.CommandFailure:
            self._is_sha(ref)

    def _is_sha(self, ref):
        if len(ref)!=40:
            raise InvalidTreeish(self.repo,ref)

        try:
                binascii.unhexlify(ref)
                ex = morphlib.execute.Execute(self.repo, self.msg)
                # TODO why is refs unused here? can we remove it?
                refs = ex.runv(['git', 'rev-list', '--no-walk', ref])
                self.sha1=ref
        except (TypeError, morphlib.execute.CommandFailure):
            raise InvalidTreeish(self.repo,ref)

def export_sources(treeish, tar_filename):
    '''Export the contents of a specific commit into a compressed tarball.'''
    ex = morphlib.execute.Execute('.', msg=logging.debug)
    ex.runv(['git', 'archive', '-o', tar_filename, '--remote', treeish.repo,
             treeish.sha1])

def get_morph_text(treeish, filename):
    '''Return a morphology from a git repository.'''
    ex = morphlib.execute.Execute(treeish.repo, msg=logging.debug)
    return ex.runv(['git', 'cat-file', 'blob', '%s:%s'
                   % (treeish.sha1, filename)])

def extract_bundle(location, bundle):
    '''Extract a bundle into git at location'''
    ex = morphlib.execute.Execute(location, msg=logging.debug)
    return ex.runv(['git', 'bundle', 'unbundle', bundle])

def clone(location, repo):
    '''clone at git repo into location'''
    ex = morphlib.execute.Execute('.', msg=logging.debug)
    return ex.runv(['git', 'clone', repo, location])

def init(location):
    '''initialise git repo at location'''
    os.mkdir(location)
    ex = morphlib.execute.Execute(location, msg=logging.debug)
    return ex.runv(['git', 'init'])

def add_remote(gitdir, name, url):
    '''add remote with name 'name' for url at gitdir'''
    ex = morphlib.execute.Execute(gitdir, msg=logging.debug)
    return ex.runv(['git', 'remote', 'add', '-f', name, url])

# FIXME: All usage of this must die and Treeishes should be used
def get_commit_id(repo, ref):
    '''Return the full SHA-1 commit id for a repo+ref.'''
    scheme, netlock, path, params, query, frag = urlparse.urlparse(repo)
    assert scheme == 'file'
    ex = morphlib.execute.Execute(path, msg=logging.debug)
    out = ex.runv(['git', 'rev-list', '-n1', ref])
    return out.strip()

