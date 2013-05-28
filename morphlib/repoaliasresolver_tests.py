# Copyright (C) 2012-2013  Codethink Limited
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
import logging
import unittest


class RepoAliasResolverTests(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.critical)
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
            ('footrove-01='
                'git://footrove.machine/%s#'
                'ssh://git@footrove.machine/%s.git'),
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

    def test_resolve_urls_for_alias_with_dash(self):
        url = self.resolver.pull_url('footrove-01:baz')
        self.assertEqual(url, 'git://footrove.machine/baz')
        url = self.resolver.push_url('footrove-01:baz')
        self.assertEqual(url, 'ssh://git@footrove.machine/baz.git')

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

    def test_ignores_malformed_aliases(self):
        resolver = morphlib.repoaliasresolver.RepoAliasResolver([
            'malformed=git://git.malformed.url.org'
        ])
        self.assertEqual(resolver.pull_url('malformed:foo'), 'malformed:foo')
        self.assertEqual(resolver.push_url('malformed:foo'), 'malformed:foo')

    def test_gets_aliases_from_interpolated_patterns(self):
        self.assertEqual(
            self.resolver.aliases_from_url('git://gitorious.org/baserock/foo'),
            ['baserock:foo'])
        self.assertEqual(
            self.resolver.aliases_from_url(
                'git@gitorious.org:baserock/foo.git'),
            ['baserock:foo'])
        self.assertEqual(
            self.resolver.aliases_from_url(
                'git://gitorious.org/baserock-morphs/bar'),
            ['upstream:bar'])
        self.assertEqual(
            self.resolver.aliases_from_url(
                'git@gitorious.org:baserock-morphs/bar.git'),
            ['upstream:bar'])

    def test_gets_aliases_from_append_pattern(self):
        self.assertEqual(
            ['append:foo'], self.resolver.aliases_from_url('git://append/foo'))
        self.assertEqual(
            ['append:foo'], self.resolver.aliases_from_url('git@append/foo'))

        self.assertEqual(
            ['append:bar'], self.resolver.aliases_from_url('git://append/bar'))
        self.assertEqual(
            ['append:bar'], self.resolver.aliases_from_url('git@append/bar'))

    def test_handles_multiple_possible_aliases(self):
        resolver = morphlib.repoaliasresolver.RepoAliasResolver([
            'trove=git://git.baserock.org/#ssh://git@git.baserock.org/',
            'baserock=git://git.baserock.org/baserock/'
                     '#ssh://git@git.baserock.org/baserock/',
        ])
        self.assertEqual(
            ['baserock:baserock/morphs', 'trove:baserock/baserock/morphs'],
            resolver.aliases_from_url(
                'git://git.baserock.org/baserock/baserock/morphs'))
