# Copyright (C) 2011  Codethink Limited
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License.
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


class SchemaError(Exception):

    pass


class Morphology(object):

    '''Represent a morphology: description of how to build binaries.'''
    
    def __init__(self, fp, baseurl=None):
        self._fp = fp
        self._baseurl = baseurl or ''
        self._load()

    def _load(self):
        logging.debug('Loading morphology %s' % self._fp.name)
        self._dict = json.load(self._fp)

        if 'name' not in self._dict:
            raise self._error('must contain "name"')
            
        if not self.name:
            raise self._error('"name" must not be empty')

        if 'kind' not in self._dict:
            raise self._error('must contain "kind"')

        if self.kind == 'chunk':
            self._validate_chunk()
        elif self.kind == 'stratum':
            self._validate_stratum()
            for source in self.sources.itervalues():
                source['repo'] = self._join_with_baseurl(source['repo'])
        else:
            raise self._error('kind must be chunk or stratum, not %s' %
                                self.kind)

        self.filename = self._fp.name

    def _validate_chunk(self):
        valid_toplevel_keys = ['name', 'kind', 'configure-commands',
                               'build-commands', 'test-commands',
                               'install-commands']

        cmdlists = [
            (self.configure_commands, 'configure-commands'),
            (self.build_commands, 'build-commands'),
            (self.test_commands, 'test-commands'),
            (self.install_commands, 'install-commands'),
        ]
        for value, name in cmdlists:
            if type(value) != list:
                raise self._error('"%s" must be a list' % name)
            for x in value:
                if type(x) != unicode:
                    raise self._error('"%s" must contain strings' % name)

        for key in self._dict.keys():
            if key not in valid_toplevel_keys:
                raise self._error('unknown key "%s"' % key)

    def _validate_stratum(self):
        valid_toplevel_keys = ['name', 'kind', 'sources']

        if 'sources' not in self._dict:
            raise self._error('stratum must contain "sources"')

        if type(self.sources) != dict:
            raise self._error('"sources" must be a dict')

        if len(self.sources) == 0:
            raise self._error('"sources" must not be empty')

        for name, source in self.sources.iteritems():
            if type(source) != dict:
                raise self._error('"sources" must contain dicts')
            if 'repo' not in source:
                raise self._error('sources must have "repo"')
            if type(source['repo']) != unicode:
                raise self._error('"repo" must be a string')
            if not source['repo']:
                raise self._error('"repo" must be a non-empty string')
            if 'ref' not in source:
                raise self._error('sources must have "ref"')
            if type(source['ref']) != unicode:
                raise self._error('"ref" must be a string')
            if not source['ref']:
                raise self._error('"ref" must be a non-empty string')
            for key in source:
                if key not in ('repo', 'ref'):
                    raise self._error('unknown key "%s" in sources' % key)

        for key in self._dict.keys():
            if key not in valid_toplevel_keys:
                raise self._error('unknown key "%s"' % key)

    @property
    def name(self):
        return self._dict['name']

    @property
    def kind(self):
        return self._dict['kind']

    @property
    def sources(self):
        return self._dict['sources']

    @property
    def configure_commands(self):
        return self._dict.get('configure-commands', [])

    @property
    def build_commands(self):
        return self._dict.get('build-commands', [])

    @property
    def test_commands(self):
        return self._dict.get('test-commands', [])

    @property
    def install_commands(self):
        return self._dict.get('install-commands', [])

    def _join_with_baseurl(self, url):
        is_relative = (':' not in url or
                       '/' not in url or
                       url.find('/') < url.find(':'))
        if is_relative:
            if not url.endswith('/'):
                url += '/'
            return self._baseurl + url
        else:
            return url

    def _error(self, msg):
        return SchemaError('Morphology %s: %s' % (self._fp.name, msg))

