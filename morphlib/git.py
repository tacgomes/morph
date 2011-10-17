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


def export_sources(repo, ref, tar_filename):
    '''Export the contents of a specific commit into a compressed tarball.'''
    ex = morphlib.execute.Execute('.', msg=logging.debug)
    tar = ex.runv(['git', 'archive', '--remote', repo, ref])
    f = gzip.open(tar_filename, 'wb')
    f.write(tar)
    f.close()


def get_commit_id(repo, ref):
    '''Return the full SHA-1 commit id for a repo+ref.'''
    # FIXME: This assume repo is a file:/// URL.

    scheme, netlock, path, params, query, frag = urlparse.urlparse(repo)
    assert scheme == 'file'
    ex = morphlib.execute.Execute(path, msg=logging.debug)
    out = ex.runv(['git', 'rev-list', '-n1', ref])
    return out.strip()

