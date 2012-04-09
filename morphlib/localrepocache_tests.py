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

import morphlib


class LocalRepoCacheTests(unittest.TestCase):

    def setUp(self):
        baseurls = ['git://example.com/']
        self.reponame = 'reponame'
        self.repourl = 'git://example.com/reponame'
        self.cachedir = '/cache/dir'
        self.cache = set()
        self.remotes = []
        self.lrc = morphlib.localrepocache.LocalRepoCache(self.cachedir,
                                                          baseurls)
        self.lrc._git = self.fake_git
        self.lrc._exists = self.fake_exists
        
    def fake_git(self, args):
        if args[0] == 'clone':
            self.assertEqual(len(args), 3)
            remote = args[1]
            local = args[2]
            if local in self.cache:
                raise Exception('cloning twice to %s' % local)
            self.remotes.append(remote)
            self.cache.add(local)
        else:
            raise NotImplementedError()
        
    def fake_exists(self, filename):
        return filename in self.cache

    def test_has_not_got_relative_repo_initially(self):
        self.assertFalse(self.lrc.has_repo(self.reponame))

    def test_has_not_got_absolute_repo_initially(self):
        self.assertFalse(self.lrc.has_repo(self.repourl))

    def test_caches_relative_repository_on_request(self):
        self.lrc.cache_repo(self.reponame)
        self.assertTrue(self.lrc.has_repo(self.reponame))
        self.assertTrue(self.lrc.has_repo(self.repourl))

    def test_caches_absolute_repository_on_request(self):
        self.lrc.cache_repo(self.repourl)
        self.assertTrue(self.lrc.has_repo(self.reponame))
        self.assertTrue(self.lrc.has_repo(self.repourl))

    def test_happily_caches_same_repo_twice(self):
        self.lrc.cache_repo(self.repourl)
        self.lrc.cache_repo(self.repourl)

    def test_fails_to_cache_when_remote_does_not_exist(self):
        def fail(args):
            raise morphlib.execute.CommandFailure('', '')
        self.lrc._git = fail
        self.assertRaises(morphlib.localrepocache.NoRemote, 
                          self.lrc.cache_repo, self.repourl)

    def test_gets_cached_relative_repo(self):
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
        e = morphlib.localrepocache.NoRemote(self.repourl)
        self.assertTrue(self.repourl in str(e))

