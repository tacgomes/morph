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


class SourceNotFound(Exception):

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
            if self.update:
                self.msg('Cached clone exists, updating origin')
                morphlib.git.update_remote(location, "origin", self.msg)
            else: # pragma: no cover
                self.msg('Cached clone exists, assuming origin is up to date')
            return True, location
        else:
            self.msg('No cached clone found, fetching from %s' % repo)

            success = False

            bundle = None
            if self.settings['bundle-server']:
                bundle_server = self.settings['bundle-server']
                if not bundle_server.endswith('/'):
                    bundle_server += '/'
                self.msg('Using bundle server %s, looking for bundle for %s' %
                         (bundle_server, name))
                bundle = name + ".bndl"
                lookup_url = urlparse.urljoin(bundle_server, bundle)
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
                    morphlib.git.init(location, self.msg)
                    self.msg('Extracting bundle %s into %s' %
                             (bundle, location))
                    morphlib.git.extract_bundle(location, bundle, self.msg)
                    self.msg('Adding origin %s' % repo)
                    morphlib.git.add_remote(location,'origin', repo, self.msg)
                else:
                    self.msg('Cloning %s into %s' % (repo, location))
                    morphlib.git.clone(location, repo, self.msg)
                success = True
            except morphlib.execute.CommandFailure:
                success = False
                    
            return success, location
            
    def _wget(self,url): # pragma: no cover
        ex = morphlib.execute.Execute(self.cache_dir, msg=self.msg)
        ex.runv(['wget', '-c', url])

    def get_treeish(self, repo, ref):
        '''Returns a Treeish for a URL or repo name with a given reference.

        If the source hasn't been cloned yet, this will fetch it, either using
        clone or by fetching a bundle. 
        
        Raises morphlib.git.InvalidTreeish if the reference cannot be found.
        Raises morphlib.sourcemanager.SourceNotFound if source cannot be found.

        '''

        # load the corresponding treeish on demand
        if (repo, ref) not in self.cached_treeishes:
            # variable for storing the loaded treeish
            treeish = None

            # try loading it from all base URLs
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
                    treeish = morphlib.git.Treeish(gitcache, repo, ref,
                                                   self.msg)

                self.indent_less()

            # if we have a treeish now, cache it to avoid loading it twice
            if treeish:
                self.cached_treeishes[(repo, ref)] = treeish
            else:
                raise SourceNotFound(repo, ref)

        # we should now have a cached treeish to use now
        return self.cached_treeishes[(repo, ref)]
