# Copyright (C) 2011-2012  Codethink Limited
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


class Morphology(object):

    '''Represent a morphology: description of how to build binaries.'''
    
    def __init__(self, treeish, fp):
        self.treeish = treeish
        self.filename = fp.name

        self._fp = fp
        self._load()

    def _load(self):
        logging.debug('Loading morphology %s from %s' % 
                      (self._fp.name, self.treeish))
        try:
            self._dict = json.load(self._fp)
        except ValueError:
            logging.error('Failed to load morphology %s from %s' % 
                          (self._fp.name, self.treeish))
            raise

        if self.kind == 'stratum':
            for source in self.sources:
                if 'repo' not in source:
                    source[u'repo'] = source['name']
                source[u'repo'] = unicode(source['repo'])

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
        return self._dict.get('build-depends', None)

    @property
    def build_system(self):
        return self._dict.get('build-system', 'manual')

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
        size = self._dict['disk-size']
        size = size.lower()
        if size.endswith('g'):
            size = int(size[:-1]) * 1024**3
        elif size.endswith('m'): # pragma: no cover
            size = int(size[:-1]) * 1024**2
        elif size.endswith('k'): # pragma: no cover
            size = int(size[:-1]) * 1024
        else: # pragma: no cover
            size = int(size)
        return size

    @property
    def test_stories(self):
        return self._dict.get('test-stories', [])

    def __eq__(self, other):
        return (self.filename == other.filename and
                self.treeish == other.treeish)

    def __hash__(self):
        return hash((self.filename, self.treeish))

    def __str__(self): # pragma: no cover
        return '%s|%s|%s' % (self.treeish.original_repo,
                             self.treeish.ref,
                             os.path.basename(self.filename))
