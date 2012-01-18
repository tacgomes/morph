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


import json
import logging
import os
import urlparse
import urllib
import urllib2
import errno

import morphlib
from morphlib.git import Treeish

gitscheme=["git",]
urlparse.uses_relative.extend(gitscheme)
urlparse.uses_netloc.extend(gitscheme)
urlparse.uses_params.extend(gitscheme)
urlparse.uses_query.extend(gitscheme)
urlparse.uses_fragment.extend(gitscheme)



class SourceManager(object):

    def __init__(self, cachedir, app):
        self.source_cache_dir = cachedir
        self.msg = app.msg
        self.settings = app.settings

    def _get_git_cache(self, repo):
        name = urllib.quote_plus(repo)
        location = self.source_cache_dir + '/' + name

        if os.path.exists(location):
            return True, location

        success=False

        self.msg('Making sure we have a local cache of the git repo')

        bundle_server = self.settings['bundle-server']
        bundle=None
        if bundle_server:
            bundle = location + ".bndl"
            lookup_url = urlparse.urljoin(bundle_server, bundle)
            self.msg('Checking for bundle %s' % lookup_url)
            req = urllib2.Request(lookup_url)
            try:
                urllib2.urlopen(req)
            except urllib2.HTTPError, e:
                bundle_exists=False
                bundle=None
            if bundle_exists:
                ex = morphlib.execute.Execute(self.source_cache_dir, msg=logging.debug)
                ex.runv(['wget', '-c', lookup_url])

        try:
            if bundle:
                morphlib.git.init(location)
                morphlib.git.extract_bundle(location, bundle)
                morphlib.git.add_remotes(location,remote)
            else:
                morphlib.git.clone(location, repo)
            success=True
        except morphlib.execute.CommandFailure:
            success=False
                
        return success, location
            

    def get_treeish(self, repo, ref):
        self.msg('checking cache for git %s|%s' % (repo, ref))

        base_urls = self.settings['git-base-url']
        success = False;

        #TODO should i check if we have full repo before or after checking with base_url?
        #TODO is it actually an error to have no base url? 
        assert(base_urls != None)

        for base_url in base_urls:    
            if success:
                break

            if not base_url.endswith('/'):
                base_url += '/'
            full_repo = urlparse.urljoin(base_url, repo)

            self.msg('cache git base_url=%s full repo url=%s' % (base_url,full_repo))
            
            success, gitcache = self._get_git_cache(full_repo);

	print "repo=%s, gitcache=%s" % (repo, gitcache)
        treeish = Treeish(gitcache, ref)
        return treeish



