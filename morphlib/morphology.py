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


class Morphology(object):

    '''Represent a morphology: description of how to build binaries.'''
    
    def __init__(self, fp, baseurl=None):
        self._fp = fp
        self._baseurl = baseurl or ''
        self._load()

    def _load(self):
        logging.debug('Loading morphology %s' % self._fp.name)
        try:
            self._dict = json.load(self._fp)
        except ValueError:
            logging.error('Failed to load morphology %s' % self._fp.name)
            raise

        if self.kind == 'stratum':
            for source in self.sources:
                if 'repo' not in source:
                    source[u'repo'] = source['name']
                repo = self._join_with_baseurl(source['repo'])
                source[u'repo'] = unicode(repo)

        self.filename = self._fp.name

    @property
    def name(self):
        return self._dict['name']

    @property
    def kind(self):
        return self._dict['kind']

    @property
    def description(self):
        return self._dict.get('description', '')

    @property
    def sources(self):
        return self._dict['sources']

    @property
    def build_depends(self):
        return self._dict.get('build-depends', [])

    @property
    def build_system(self):
        return self._dict.get('build-system', None)

    @property
    def max_jobs(self):
        if 'max-jobs' in self._dict:
            return int(self._dict['max-jobs'])
        return None

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

    @property
    def chunks(self):
        return self._dict.get('chunks', {})

    @property
    def strata(self):
        return self._dict.get('strata', [])

    @property
    def disk_size(self):
        return self._dict['disk-size']

    @property
    def test_stories(self):
        return self._dict.get('test-stories', [])

    def _join_with_baseurl(self, url):
        is_relative = (':' not in url or
                       '/' not in url or
                       url.find('/') < url.find(':'))
        if is_relative:
            if not url.endswith('/'):
                url += '/'
            baseurl = self._baseurl
            if baseurl and not baseurl.endswith('/'):
                baseurl += '/'
            return baseurl + url
        else:
            return url

