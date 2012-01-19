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
from morphlib.git import Treeish


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

    def __init__(self, cachedir, app):
        self.source_cache_dir = cachedir
        self.msg = app.msg
        self.settings = app.settings

    def _get_git_cache(self, repo):
        name = quote_url(repo)
        location = self.source_cache_dir + '/' + name

        if os.path.exists(location):
            return True, location

        success = False

        self.msg('Making sure we have a local cache of the git repo')

        bundle = None
        if self.settings.has_key('bundle-server'):
            bundle_server = self.settings['bundle-server']
            if not bundle_server.endswith('/'):
                bundle_server += '/'
            self.msg("Using bundle server %s, looking for bundle for %s" %
                     (bundle_server, name))
            bundle = name + ".bndl"
            lookup_url = urlparse.urljoin(bundle_server, bundle)
            self.msg('Checking for bundle %s' % lookup_url)
            req = urllib2.Request(lookup_url)

            try:
                urllib2.urlopen(req)
                self._wget(lookup_url)
                bundle = self.source_cache_dir + '/' + bundle
            except urllib2.URLError:
                self.msg("Unable to find bundle %s on %s" %
                         (bundle, bundle_server))
                bundle = None
        try:
            if bundle:
                self.msg("initialising git repo at %s" % location)
                morphlib.git.init(location)
                self.msg("extracting bundle %s into %s" % (bundle, location))
                morphlib.git.extract_bundle(location, bundle)
                self.msg("adding origin %s" % repo)
                morphlib.git.add_remote(location,'origin', repo)
            else:
                self.msg("cloning %s into %s" % (repo, location))
                morphlib.git.clone(location, repo)
            success = True
        except morphlib.execute.CommandFailure:
            success = False
                
        return success, location
            
    def _wget(self,url): # pragma: no cover
        ex = morphlib.execute.Execute(self.source_cache_dir, msg=self.msg)
        ex.runv(['wget', '-c', url])

    def get_treeish(self, repo, ref):
        self.msg('checking cache for git %s|%s' % (repo, ref))

        #TODO is it actually an error to have no base url? 
        base_urls = self.settings['git-base-url']
        success = False;

        for base_url in base_urls:    
            if success:
                self.msg("success!")
                break

            self.msg("looking in base url %s" % base_url)

            if not base_url.endswith('/'):
                base_url += '/'
            full_repo = urlparse.urljoin(base_url, repo)

            self.msg('cache git base_url=\'%s\' full repo url=\'%s\'' %
                     (base_url,full_repo))
            
            success, gitcache = self._get_git_cache(full_repo);

        if not success:
            raise SourceNotFound(repo,ref)

        self.msg("creating treeish for %s ref %s" % (gitcache,ref))
        treeish = Treeish(gitcache, ref, self.msg)
        return treeish
