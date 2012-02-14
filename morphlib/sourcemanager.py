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


class RepositoryUpdateError(Exception): # pragma: no cover

    def __init__(self, repo, ref, error):
        Exception.__init__(self, 'Failed to update %s:%s: %s' %
                           (repo, ref, error))


class RepositoryFetchError(Exception):

    def __init__(self, repo):
        Exception.__init__(self, 'Failed to fetch %s' % repo)


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

    def _wget(self, url): # pragma: no cover
        # the following doesn't work during bootstrapping
        # ex = morphlib.execute.Execute(self.cache_dir, msg=self.msg)
        # ex.runv(['wget', '-c', url])
        # so we do it poorly in pure Python instead
        t = urlparse.urlparse(url)
        path = t[2]
        basename = os.path.basename(path)
        saved_name = os.path.join(self.cache_dir, basename)

        source_handle = urllib2.urlopen(url)
        target_handle = open(saved_name, 'wb')

        data = source_handle.read(4096)
        while data:
            target_handle.write(data)
            data = source_handle.read(4096)

        source_handle.close()
        target_handle.close()

        return saved_name

    def _cache_repo_from_bundle(self, server, repo_url):
        quoted_url = quote_url(repo_url)
        cached_repo = os.path.join(self.cache_dir, quoted_url)
        bundle_name = '%s.bndl' % quoted_url
        bundle_url = server + bundle_name
        self.msg('Trying to fetch bundle %s' % bundle_url)
        request = urllib2.Request(bundle_url)
        try:
            urllib2.urlopen(request)
            try:
                bundle = self._wget(bundle_url)
                self.msg('Extracting bundle %s into %s' %
                         (bundle, cached_repo))
                try:
                    os.mkdir(cached_repo)
                    print cached_repo, bundle, self.msg
                    morphlib.git.extract_bundle(cached_repo, bundle,
                                                self.msg)
                    self.msg('Setting origin to %s' % repo_url)
                    morphlib.git.set_remote(cached_repo, 'origin',
                                            repo_url, self.msg)
                    return cached_repo
                except morphlib.execute.CommandFailure, e: # pragma: no cover
                    self.msg('Unable to extract bundle %s: %s' %
                             (bundle, e))
                    return None
            except morphlib.execute.CommandFailure, e: # pragma: no cover
                self.msg('Unable to fetch bundle %s: %s' %
                         (bundle_url, e))
                return None
        except urllib2.URLError, e:
            self.msg('Unable to fetch bundle %s: %s' % (bundle_url, e))
            return None

    def _cache_repo_from_url(self, repo_url):
        # quote the URL and calculate the location for the cached repo
        quoted_url = quote_url(repo_url)
        cached_repo = os.path.join(self.cache_dir, quoted_url)

        if os.path.exists(cached_repo): # pragma: no cover
            # the cache location exists, assume this is what we want
            self.msg('Using cached clone %s of %s' % (cached_repo, repo_url))
            return cached_repo
        else:
            # bundle server did not have a bundle for the repo
            self.msg('Cloning %s into %s' % (repo_url, cached_repo))
            try:
                morphlib.git.clone(cached_repo, repo_url, self.msg)
                return cached_repo
            except morphlib.execute.CommandFailure, e:
                self.msg('Failed to clone from %s: %s' % (repo_url, e))
                return None

    def _cache_repo_from_base_urls(self, repo, ref):
        self.msg('Checking repository %s' % repo)
        self.indent_more()
>>>>>>> a4ff907... Rewrite get_treeish(), fetching and update code.

        def fixup_url(url):
            return (url if url.endswith('/') else url + '/')

        # create absolute repo URLs
        repo_urls = [urlparse.urljoin(fixup_url(x), repo)
                     for x in self.settings['git-base-url']]

        cached_repo = None

        # check if we have a cached version of the repo
        for repo_url in repo_urls:
            quoted_url = quote_url(repo_url)
            cached_repo_dirname = os.path.join(self.cache_dir, quoted_url)
            if os.path.exists(cached_repo_dirname):
                cached_repo = cached_repo_dirname
                break

        # first pass, try all base URLs with the bundle server
        if not cached_repo and self.settings['bundle-server']:
            server = fixup_url(self.settings['bundle-server'])

            for repo_url in repo_urls:
                cached_repo = self._cache_repo_from_bundle(server, repo_url)
                if cached_repo:
                    break

        # second pass, try cloning from base URLs directly
        if not cached_repo:
            # try all URLs to find or obtain a cached clone of the repo
            for repo_url in repo_urls:
                cached_repo = self._cache_repo_from_url(repo_url)
                if cached_repo:
                    break

        if cached_repo:
            # we have a cached version of the repo now
            if self.update:
                # we are supposed to update 'origin', so do that now
                try:
                    self.msg('Updating %s' % cached_repo)
                    morphlib.git.update_remote(cached_repo, 'origin',
                                               self.msg)
                except morphlib.execute.CommandFailure, e: # pragma: no cover
                    self.indent_less()
                    raise RepositoryUpdateError(repo, ref, e)
            else: # pragma: no cover
                self.msg('Assuming cached repository %s is up to date' %
                         cached_repo)
        else: # pragma: no cover
            # cloning using all individual base URLs failed
            self.indent_less()
            raise RepositoryFetchError(repo)

        # we should have a cached version of the repo now, return a treeish
        # for the repo and ref tuple
        treeish = morphlib.git.Treeish(cached_repo, repo, ref, self.msg)
        self.indent_less()
        return treeish

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
            treeish = self._cache_repo_from_base_urls(repo, ref)

            # have a treeish now, cache it to avoid loading it twice
            self.cached_treeishes[(repo, ref)] = treeish

            # load tree-ishes for submodules, if necessary and desired
            if self.settings['ignore-submodules']:
                treeish.submodules = []
            else:
                self._resolve_submodules(treeish)

        # we should now have a cached treeish to use now
        return self.cached_treeishes[(repo, ref)] # pragma: no cover
