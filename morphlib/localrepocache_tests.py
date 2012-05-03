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


import unittest
import urllib2

import morphlib


class LocalRepoCacheTests(unittest.TestCase):

    def setUp(self):
        aliases = ['upstream=git://example.com/%s#example.com:%s.git']
        bundle_base_url = 'http://lorry.example.com/bundles/'
        self.reponame = 'upstream:reponame'
        self.repourl = 'git://example.com/reponame'
        self.pushurl = 'example.com:reponame.git'
        escaped_url = 'git___example_com_reponame'
        self.bundle_url = '%s%s.bndl' % (bundle_base_url, escaped_url)
        self.cachedir = '/cache/dir'
        self.cache_path = '%s/%s' % (self.cachedir, escaped_url)
        self.cache = set()
        self.remotes = {}
        self.fetched = []
        self.removed = []
        self.lrc = morphlib.localrepocache.LocalRepoCache(self.cachedir,
                                                          aliases,
                                                          bundle_base_url)
        self.lrc._git = self.fake_git
        self.lrc._exists = self.fake_exists
        self.lrc._fetch = self.not_found
        self.lrc._mkdir = self.fake_mkdir
        self.lrc._remove = self.fake_remove
        
    def fake_git(self, args, cwd=None):
        if args[0] == 'clone':
            self.assertEqual(len(args), 4)
            remote = args[2]
            local = args[3]
            if local in self.cache:
                raise Exception('cloning twice to %s' % local)
            self.remotes['origin'] = {'url': remote, 'updates': 0}
            self.cache.add(local)
        elif args[0:2] == ['remote', 'set-url']:
            remote = args[2]
            url = args[3]
            self.remotes[remote]['url'] = url
        else:
            raise NotImplementedError()
        
    def fake_exists(self, filename):
        return filename in self.cache

    def fake_mkdir(self, dirname):
        self.cache.add(dirname)

    def fake_remove(self, filename):
        self.removed.append(filename)

    def not_found(self, url, path):
        raise urllib2.URLError('Not found')

    def fake_fetch(self, url, path):
        self.fetched.append(url)
        self.cache.add(path)
        return True

    def test_expands_shortened_url_correctly_for_pulling(self):
        self.assertEqual(self.lrc.pull_url(self.reponame), self.repourl)

    def test_expands_shortened_url_correctly_for_pushing(self):
        self.assertEqual(self.lrc.push_url(self.reponame), self.pushurl)

    def test_has_not_got_shortened_repo_initially(self):
        self.assertFalse(self.lrc.has_repo(self.reponame))

    def test_has_not_got_absolute_repo_initially(self):
        self.assertFalse(self.lrc.has_repo(self.repourl))

    def test_caches_shortened_repository_on_request(self):
        self.lrc.cache_repo(self.reponame)
        self.assertTrue(self.lrc.has_repo(self.reponame))
        self.assertTrue(self.lrc.has_repo(self.repourl))

    def test_caches_absolute_repository_on_request(self):
        self.lrc.cache_repo(self.repourl)
        self.assertTrue(self.lrc.has_repo(self.reponame))
        self.assertTrue(self.lrc.has_repo(self.repourl))

    def test_cachedir_does_not_exist_initially(self):
        self.assertFalse(self.cachedir in self.cache)

    def test_creates_cachedir_if_missing(self):
        self.lrc.cache_repo(self.repourl)
        self.assertTrue(self.cachedir in self.cache)

    def test_happily_caches_same_repo_twice(self):
        self.lrc.cache_repo(self.repourl)
        self.lrc.cache_repo(self.repourl)

    def test_fails_to_cache_when_remote_does_not_exist(self):
        def fail(args):
            raise morphlib.execute.CommandFailure('', '')
        self.lrc._git = fail
        self.assertRaises(morphlib.localrepocache.NoRemote, 
                          self.lrc.cache_repo, self.repourl)

    def test_does_not_mind_a_missing_bundle(self):
        self.lrc.cache_repo(self.repourl)
        self.assertEqual(self.fetched, [])

    def test_fetches_bundle_when_it_exists(self):
        self.lrc._fetch = self.fake_fetch
        self.lrc.cache_repo(self.repourl)
        self.assertEqual(self.fetched, [self.bundle_url])
        self.assertEqual(self.removed, [self.cache_path + '.bundle'])
        self.assertEqual(self.remotes['origin']['url'], self.repourl)

    def test_gets_cached_shortened_repo(self):
        self.lrc.cache_repo(self.reponame)
        cached = self.lrc.get_repo(self.reponame)
        self.assertTrue(cached is not None)

    def test_gets_cached_absolute_repo(self):
        self.lrc.cache_repo(self.repourl)
        cached = self.lrc.get_repo(self.repourl)
        self.assertTrue(cached is not None)

    def test_get_repo_raises_exception_if_repo_is_not_cached(self):
        self.assertRaises(Exception, self.lrc.get_repo, self.repourl)

    def test_escapes_repourl_as_filename(self):
        escaped = self.lrc._escape(self.repourl)
        self.assertFalse('/' in escaped)

    def test_noremote_error_message_contains_repo_name(self):
        e = morphlib.localrepocache.NoRemote(self.repourl, [])
        self.assertTrue(self.repourl in str(e))

