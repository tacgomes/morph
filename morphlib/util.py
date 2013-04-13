# Copyright (C) 2011-2013  Codethink Limited
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

import re

import morphlib
import logging

'''Utility functions for morph.'''


# It is intentional that if collections does not have OrderedDict that
# simplejson is also used in preference to json, as OrderedDict became
# a member of collections in the same release json got its object_pairs_hook
try: # pragma: no cover
    from collections import OrderedDict
    import json
except ImportError: # pragma: no cover
    from ordereddict import OrderedDict
    import simplejson as json

try:
    from multiprocessing import cpu_count
except NotImplementedError:  # pragma: no cover
    cpu_count = lambda: 1
import os


def indent(string, spaces=4):
    '''Return ``string`` indented by ``spaces`` spaces.

    The final line is not terminated by a newline. This makes it easy
    to use this function for indenting long text for logging: the
    logging library adds a newline, so not including it in the indented
    text avoids a spurious empty line in the log file.

    This also makes the result be a plain ASCII encoded string.

    '''

    if type(string) == unicode:  # pragma: no cover
        string = string.decode('utf-8')
    lines = string.splitlines()
    lines = ['%*s%s' % (spaces, '', line) for line in lines]
    return '\n'.join(lines)


def make_concurrency(cores=None):
    '''Return the number of concurrent jobs for make.

    This will be given to make as the -j argument.

    '''

    n = cpu_count() if cores is None else cores
    # Experimental results (ref. Kinnison) says a factor of 1.5
    # gives about the optimal result for build times, since much of
    # builds are I/O bound, not CPU bound.
    return max(int(n * 1.5 + 0.5), 1)


def create_cachedir(settings):  # pragma: no cover
    '''Return cache directory, creating it if necessary.'''

    cachedir = settings['cachedir']
    if not os.path.exists(cachedir):
        os.mkdir(cachedir)
    return cachedir


def new_artifact_caches(settings):  # pragma: no cover
    '''Create new objects for local and remote artifact caches.

    This includes creating the directories on disk, if missing.

    '''

    cachedir = create_cachedir(settings)
    artifact_cachedir = os.path.join(cachedir, 'artifacts')
    if not os.path.exists(artifact_cachedir):
        os.mkdir(artifact_cachedir)

    lac = morphlib.localartifactcache.LocalArtifactCache(artifact_cachedir)

    rac_url = settings['cache-server']
    if rac_url:
        rac = morphlib.remoteartifactcache.RemoteArtifactCache(rac_url)
    else:
        rac = None
    return lac, rac


def combine_aliases(app):  # pragma: no cover
    '''Create a full repo-alias set from the app's settings.'''
    trove_host = app.settings['trove-host']
    trove_ids = app.settings['trove-id']
    repo_aliases = app.settings['repo-alias']
    repo_pat = r'^(?P<prefix>[a-z0-9]+)=(?P<pull>[^#]+)#(?P<push>[^#]+)$'
    trove_pat = (r'^(?P<prefix>[a-z0-9]+)=(?P<path>[^#]+)#'
                 '(?P<pull>[^#]+)#(?P<push>[^#]+)$')
    alias_map = {}
    def _expand(protocol, path):
        if protocol == "git":
            return "git://%s/%s/%%s" % (trove_host, path)
        elif protocol == "ssh":
            return "ssh://git@%s/%s/%%s" % (trove_host, path)
        else:
            raise cliapp.AppException(
                'Unknown protocol in trove_id: %s' % protocol)

    if trove_host:
        alias_map['baserock'] = "baserock=%s#%s" % (
            _expand('git', 'baserock'),
            _expand('ssh', 'baserock'))
        alias_map['upstream'] = "upstream=%s#%s" % (
            _expand('git', 'delta'),
            _expand('ssh', 'delta'))
        for trove_id in trove_ids:
            m = re.match(trove_pat, trove_id)
            if m:
                alias_map[m.group('prefix')] = "%s=%s#%s" % (
                    m.group('prefix'),
                    _expand(m.group('pull'), m.group('path')),
                    _expand(m.group('push'), m.group('path')))
            elif '=' not in trove_id:
                alias_map[trove_id] = "%s=%s#%s" % (
                    trove_id,
                    _expand('ssh', trove_id),
                    _expand('ssh', trove_id))
    for repo_alias in repo_aliases:
        m = re.match(repo_pat, repo_alias)
        if m:
            alias_map[m.group('prefix')] = repo_alias

    return alias_map.values()

def new_repo_caches(app):  # pragma: no cover
    '''Create new objects for local, remote git repository caches.'''

    aliases = app.settings['repo-alias']
    cachedir = create_cachedir(app.settings)
    gits_dir = os.path.join(cachedir, 'gits')
    tarball_base_url = app.settings['tarball-server']
    repo_resolver = morphlib.repoaliasresolver.RepoAliasResolver(aliases)
    lrc = morphlib.localrepocache.LocalRepoCache(
        app, gits_dir, repo_resolver, tarball_base_url=tarball_base_url)

    url = app.settings['cache-server']
    if url:
        rrc = morphlib.remoterepocache.RemoteRepoCache(url, repo_resolver)
    else:
        rrc = None

    return lrc, rrc


def log_dict_diff(cur, pre): # pragma: no cover
    '''Log the differences between two dicts to debug log'''
    dictA = cur
    dictB = pre
    for key in dictA.keys():
        if key not in dictB:
            logging.debug("New environment: %s = %s" % (key, dictA[key]))
        elif dictA[key] != dictB[key]:
            logging.debug(
                "Environment changed: %(key)s = %(valA)s to %(key)s = %(valB)s"
                % {"key": key, "valA": dictA[key], "valB": dictB[key]})
    for key in dictB.keys():
        if key not in dictA:
            logging.debug("Environment removed:  %s = %s" % (key, dictB[key]))


# This acquired from rdiff-backup which is GPLv2+ and a patch from 2011
# which has not yet been merged, combined with a tad of tidying from us.
def copyfileobj(inputfp, outputfp, blocksize=1024*1024):  # pragma: no cover
    """Copies file inputfp to outputfp in blocksize intervals"""

    sparse = False
    buf = None
    while 1:
        inbuf = inputfp.read(blocksize)
        if not inbuf: break
        if not buf: 
            buf = inbuf
        else:
            buf += inbuf
            
        # Combine "short" reads
        if (len(buf) < blocksize):
            continue
            
        buflen = len(buf)
        if buf == "\x00" * buflen:
            outputfp.seek(buflen, os.SEEK_CUR)
            buf = None
            # flag sparse=True, that we seek()ed, but have not written yet
            # The filesize is wrong until we write
            sparse = True 
        else:
            outputfp.write(buf)
            buf = None
            # We wrote, so clear sparse.
            sparse = False
            
    if buf:
        outputfp.write(buf)
    elif sparse:
        outputfp.seek(-1, os.SEEK_CUR)
        outputfp.write("\x00")
