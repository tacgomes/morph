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


import morphlib
import unittest


class RepoAliasResolverTests(unittest.TestCase):

    def setUp(self):
        self.aliases = [
            ('upstream='
                'git://gitorious.org/baserock-morphs/%s#'
                'git@gitorious.org:baserock-morphs/%s.git'),
            ('baserock='
                'git://gitorious.org/baserock/%s#'
                'git@gitorious.org:baserock/%s.git'),
            ('append='
                'git://append/#'
                'git@append/'),
        ]
        self.resolver = morphlib.repoaliasresolver.RepoAliasResolver(
            self.aliases)

    def test_resolve_urls_without_alias_prefix(self):
        self.assertEqual(self.resolver.pull_url('bar'), 'bar')
        self.assertEqual(self.resolver.push_url('bar'), 'bar')

        self.assertEqual(self.resolver.pull_url('foo'), 'foo')
        self.assertEqual(self.resolver.push_url('foo'), 'foo')

    def test_resolve_urls_for_repos_of_one_alias(self):
        url = self.resolver.pull_url('upstream:foo')
        self.assertEqual(url, 'git://gitorious.org/baserock-morphs/foo')
        url = self.resolver.push_url('upstream:foo')
        self.assertEqual(url, 'git@gitorious.org:baserock-morphs/foo.git')

        url = self.resolver.pull_url('upstream:bar')
        self.assertEqual(url, 'git://gitorious.org/baserock-morphs/bar')
        url = self.resolver.push_url('upstream:bar')
        self.assertEqual(url, 'git@gitorious.org:baserock-morphs/bar.git')

    def test_resolve_urls_for_repos_of_another_alias(self):
        url = self.resolver.pull_url('baserock:foo')
        self.assertEqual(url, 'git://gitorious.org/baserock/foo')
        url = self.resolver.push_url('baserock:foo')
        self.assertEqual(url, 'git@gitorious.org:baserock/foo.git')

        url = self.resolver.pull_url('baserock:bar')
        self.assertEqual(url, 'git://gitorious.org/baserock/bar')
        url = self.resolver.push_url('baserock:bar')
        self.assertEqual(url, 'git@gitorious.org:baserock/bar.git')

    def test_resolve_urls_for_unknown_alias(self):
        self.assertEqual(self.resolver.pull_url('unknown:foo'), 'unknown:foo')
        self.assertEqual(self.resolver.push_url('unknown:foo'), 'unknown:foo')

        self.assertEqual(self.resolver.pull_url('unknown:bar'), 'unknown:bar')
        self.assertEqual(self.resolver.push_url('unknown:bar'), 'unknown:bar')

    def test_resolve_urls_for_pattern_without_placeholder(self):
        self.assertEqual(
            self.resolver.pull_url('append:foo'), 'git://append/foo')
        self.assertEqual(
            self.resolver.push_url('append:foo'), 'git@append/foo')

        self.assertEqual(
            self.resolver.pull_url('append:bar'), 'git://append/bar')
        self.assertEqual(
            self.resolver.push_url('append:bar'), 'git@append/bar')
