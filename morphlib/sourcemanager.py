# Copyright (C) 2012  Codethink Limited
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
import os
import urlparse
import urllib2
import string

import morphlib


gitscheme=["git",]
urlparse.uses_relative.extend(gitscheme)
urlparse.uses_netloc.extend(gitscheme)
urlparse.uses_params.extend(gitscheme)
urlparse.uses_query.extend(gitscheme)
urlparse.uses_fragment.extend(gitscheme)

_valid_chars = string.digits + string.letters + ':%_'


def quote_url(url):
    transl = lambda x: x if x in _valid_chars else '_'
    return ''.join([transl(x) for x in url])


class RepositoryUpdateError(Exception):

    def __init__(self, repo, ref):
        Exception.__init__(self, 'No source found at %s:%s' % (repo, ref))


class SourceManager(object):

    def __init__(self, app, cachedir=None, update=True):
        self.real_msg = app.msg
        self.settings = app.settings
        self.cached_treeishes = {}
        self.cache_dir = cachedir 
        self.update = update
        if not self.cache_dir:
            self.cache_dir = os.path.join(app.settings['cachedir'], 'gits')
        self.indent = 0

    def indent_more(self):
        self.indent += 1
    
    def indent_less(self):
        self.indent -= 1

    def msg(self, text):
        spaces = '  ' * self.indent
        self.real_msg('%s%s' % (spaces, text))

    def _get_git_cache(self, repo):
        name = quote_url(repo)
        location = self.cache_dir + '/' + name

        if os.path.exists(location):
            if self.update: # pragma: no cover
                self.msg('Cached clone exists, updating origin')
                try:
                    morphlib.git.update_remote(location, "origin", self.msg)
                except morphlib.execute.CommandFailure, e: # pragma: no cover
                    logging.warning('Ignoring git error:\n%s' % str(e))
            else: # pragma: no cover
                self.msg('Cached clone exists, assuming origin is up to date')
            return True, location # pragma: no cover
        else:
            if self.update:
                self.msg('No cached clone found, fetching from %s' % repo)

                success = False

                bundle = None
                if self.settings['bundle-server']:
                    bundle_server = self.settings['bundle-server']
                    if not bundle_server.endswith('/'):
                        bundle_server += '/'
                    self.msg('Using bundle server %s, looking for bundle '
                             'for %s' % (bundle_server, name))
                    bundle = name + ".bndl"
                    lookup_url = bundle_server + bundle
                    self.msg('Checking for bundle %s' % lookup_url)
                    req = urllib2.Request(lookup_url)

                    try:
                        urllib2.urlopen(req)
                        self._wget(lookup_url)
                        bundle = self.cache_dir + '/' + bundle
                    except urllib2.URLError:
                        self.msg('Unable to find bundle %s on %s' %
                                 (bundle, bundle_server))
                        bundle = None
                try:
                    if bundle:
                        self.msg('Initialising repository at %s' % location)
                        os.mkdir(location)
                        self.msg('Extracting bundle %s into %s' %
                                 (bundle, location))
                        morphlib.git.extract_bundle(location, bundle, self.msg)
                        self.msg('Setting origin to %s' % repo)
                        morphlib.git.set_remote(location,'origin', repo,
                                                self.msg)
                        self.msg('Updating from origin')
                        try:
                            morphlib.git.update_remote(location, "origin",
                                                       self.msg)
                        except morphlib.execute.CommandFailure, e: # pragma: no cover
                            logging.warning('Ignoring git failure:\n%s' %
                                            str(e))
                    else:
                        self.msg('Cloning %s into %s' % (repo, location))
                        morphlib.git.clone(location, repo, self.msg)
                    success = True
                except morphlib.execute.CommandFailure:
                    success = False
            else: # pragma: no cover
                self.msg('No cached clone found, skipping this location')
                success = False
                    
            return success, location
            
    def _wget(self, url): # pragma: no cover
        # the following doesn't work during bootstrapping
        # ex = morphlib.execute.Execute(self.cache_dir, msg=self.msg)
        # ex.runv(['wget', '-c', url])
        # so we do it poorly in pure Python instead
        f = urllib2.urlopen(url)
        data = f.read()
        f.close()
        t = urlparse.urlparse(url)
        path = t[2]
        basename = os.path.basename(path)
        saved_name = os.path.join(self.cache_dir, basename)
        with open(saved_name, 'wb') as f:
            f.write(data)

    def _cache_git_from_base_urls(self, repo, ref):
        treeish = None

        # try all base URLs to load the treeish
        for base_url in self.settings['git-base-url']:
            # generate the full repo URL
            if not base_url.endswith('/'):
                base_url += '/'
            full_repo = urlparse.urljoin(base_url, repo)

            self.msg('Updating repository %s' % quote_url(full_repo))
            self.indent_more()

            # try to clone/update the repo so that we can obtain a treeish
            success, gitcache = self._get_git_cache(full_repo)
            if success:
                treeish = morphlib.git.Treeish(gitcache, repo, ref, self.msg)
                self.indent_less()
                break

            self.indent_less()

        if treeish:
            return treeish
        else:
            raise RepositoryUpdateError(repo, ref)

    def _resolve_submodules(self, treeish): # pragma: no cover
        self.indent_more()

        # resolve submodules
        treeish.submodules = morphlib.git.Submodules(treeish, self.msg)
        try:
            # load submodules from .gitmodules
            treeish.submodules.load()

            # resolve the tree-ishes for all submodules recursively
            for submodule in treeish.submodules: # pragma: no cover
                submodule.treeish = self.get_treeish(submodule.url,
                                                     submodule.commit)
        except morphlib.git.NoModulesFileError:
            # this is not really an error, the repository simply
            # does not specify any git submodules
            pass

        self.indent_less()

    def get_treeish(self, repo, ref):
        '''Returns a Treeish for a URL or repo name with a given reference.

        If the source hasn't been cloned yet, this will fetch it, either using
        clone or by fetching a bundle. 
        
        Raises morphlib.git.InvalidReferenceError if the reference cannot be
        found. Raises morphlib.sourcemanager.RepositoryUpdateError if the
        repository cannot be cloned or updated.

        '''

        if (repo, ref) not in self.cached_treeishes: # pragma: no cover
            # load the corresponding treeish on demand
            treeish = self._cache_git_from_base_urls(repo, ref)

            # have a treeish now, cache it to avoid loading it twice
            self.cached_treeishes[(repo, ref)] = treeish

            # load tree-ishes for submodules, if necessary and desired
            if self.settings['ignore-submodules']:
                treeish.submodules = []
            else:
                self._resolve_submodules(treeish)

        # we should now have a cached treeish to use now
        return self.cached_treeishes[(repo, ref)] # pragma: no cover
