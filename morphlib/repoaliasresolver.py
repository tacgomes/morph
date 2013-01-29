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


import logging
import re


class RepoAlias(object):

    def __init__(self, alias, prefix, pullpat, pushpat):
        self.alias = alias
        self.prefix = prefix
        self.pullpat = pullpat
        self.pushpat = pushpat


class RepoAliasResolver(object):

    def __init__(self, aliases):
        self.aliases = {}

        alias_pattern = (r'^(?P<prefix>[a-z0-9]+)'
                         r'=(?P<pullpat>[^#]+)#(?P<pushpat>[^#]+)$')
        for alias in aliases:
            logging.debug('expanding: alias="%s"' % alias)
            m = re.match(alias_pattern, alias)
            logging.debug('expanding: m=%s' % repr(m))
            if not m:
                logging.warning('Alias %s is malformed' % alias)
                continue
            prefix = m.group('prefix')
            logging.debug('expanding: prefix group=%s' % prefix)
            self.aliases[prefix] = RepoAlias(alias, prefix, m.group('pullpat'),
                                             m.group('pushpat'))


    def pull_url(self, reponame):
        '''Expand a possibly shortened repo name to a pull url.'''
        return self._expand_reponame(reponame, 'pullpat')

    def push_url(self, reponame):
        '''Expand a possibly shortened repo name to a push url.'''
        return self._expand_reponame(reponame, 'pushpat')

    def _expand_reponame(self, reponame, patname):
        logging.debug('expanding: reponame=%s' % reponame)
        logging.debug('expanding: patname=%s' % patname)

        prefix, suffix = self._split_reponame(reponame)
        logging.debug('expanding: prefix=%s' % prefix)
        logging.debug('expanding: suffix=%s' % suffix)

        # There was no prefix.
        if prefix is None:
            logging.debug('expanding: no prefix')
            return reponame

        if prefix not in self.aliases:
            # Unknown prefix. Which means it may be a real URL instead.
            # Let the caller deal with it.
            logging.debug('expanding: unknown prefix')
            return reponame

        pat = getattr(self.aliases[prefix], patname)
        return self._apply_url_pattern(pat, suffix)


    def _split_reponame(self, reponame):
        '''Split reponame into prefix and suffix.

        The prefix is returned as None if there was no prefix.

        '''

        pat = r'^(?P<prefix>[a-z0-9]+):(?P<rest>.*)$'
        m = re.match(pat, reponame)
        if m:
            return m.group('prefix'), m.group('rest')
        else:
            return None, reponame

    def _apply_url_pattern(self, pattern, shortname):
        if '%s' in pattern:
            return shortname.join(pattern.split('%s'))
        else:
            return pattern + shortname
