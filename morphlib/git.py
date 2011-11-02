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


import gzip
import logging
import urlparse

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


def export_sources(repo, ref, tar_filename):
    '''Export the contents of a specific commit into a compressed tarball.'''
    ex = morphlib.execute.Execute('.', msg=logging.debug)
    tar = ex.runv(['git', 'archive', '--remote', repo, ref])
    f = gzip.open(tar_filename, 'wb')
    f.write(tar)
    f.close()


def get_commit_id(repo, ref):
    '''Return the full SHA-1 commit id for a repo+ref.'''
    # FIXME: This assumes repo is a file:/// URL.

    scheme, netlock, path, params, query, frag = urlparse.urlparse(repo)
    assert scheme == 'file'
    ex = morphlib.execute.Execute(path, msg=logging.debug)
    out = ex.runv(['git', 'rev-list', '-n1', ref])
    return out.strip()


def get_morph_text(repo, ref, filename):
    '''Return a morphology from a git repository.'''
    # FIXME: This implementation assumes a local repo.

    scheme, netlock, path, params, query, frag = urlparse.urlparse(repo)
    assert scheme == 'file'
    ex = morphlib.execute.Execute(path, msg=logging.debug)
    return ex.runv(['git', 'cat-file', 'blob', '%s:%s' % (ref, filename)])

