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


import logging
import os

import morphlib


class Builder(object):

    '''Build binary objects for Baserock.
    
    The objects may be chunks or strata.'''
    
    def __init__(self, tempdir, msg, settings):
        self.tempdir = tempdir
        self.msg = msg
        self.settings = settings
        self.cachedir = morphlib.cachedir.CacheDir(settings['cachedir'])

    @property
    def arch(self):
        return os.uname()[4]

    def build(self, morph):
        '''Build a binary based on a morphology.'''
        if morph.kind == 'chunk':
            self.build_chunk(morph, self.settings['chunk-repo'], 
                             self.settings['chunk-ref'])
        elif morph.kind == 'stratum':
            self.build_stratum(morph)
        else:
            raise Exception('Unknown kind of morphology: %s' % morph.kind)

    def build_chunk(self, morph, repo, ref):
        '''Build a chunk from a morphology.'''
        logging.debug('Building chunk')
        self.ex = morphlib.execute.Execute(self._build, self.msg)
        self.ex.env['WORKAREA'] = self.tempdir.dirname
        self.ex.env['DESTDIR'] = self._inst + '/'
        self.create_build_tree(morph, repo, ref)
        self.ex.run(morph.configure_commands)
        self.ex.run(morph.build_commands)
        self.ex.run(morph.test_commands)
        self.ex.run(morph.install_commands)
        self.create_chunk(morph, repo, ref)
        self.tempdir.clear()
        
    def create_build_tree(self, morph, repo, ref):
        '''Export sources from git into the ``self._build`` directory.'''

        logging.debug('Creating build tree at %s' % self._build)
        tarball = self.tempdir.join('sources.tar')
        self.ex.runv(['git', 'archive',
                      '--output', tarball,
                      '--remote', repo,
                      ref])
        os.mkdir(self._build)
        self.ex.runv(['tar', '-C', self._build, '-xf', tarball])
        os.remove(tarball)

    def create_chunk(self, morph, repo, ref):
        '''Create a Baserock chunk from the ``self._inst`` directory.
        
        The directory must be filled in with all the relevant files already.
        
        '''

        filename = self.get_cached_name('chunk', repo, ref)
        logging.debug('Creating chunk %s at %s' % (morph.name, filename))
        self.ex.runv(['tar', '-C', self._inst, '-czf', filename, '.'])

    def build_stratum(self, morph):
        '''Build a stratum from a morphology.'''
        os.mkdir(self._inst)
        self.ex = morphlib.execute.Execute(self.tempdir.dirname, self.msg)
        for chunk_name in morph.sources:
            chunk_repo = self.settings['chunk-repo']
            chunk_ref = self.settings['chunk-ref']
            filename = self.get_cached_name('chunk', chunk_repo, chunk_ref)
            self.unpack_chunk(filename)
        self.create_stratum(morph)
        self.tempdir.clear()

    def unpack_chunk(self, filename):
        self.ex.runv(['tar', '-C', self._inst, '-xf', filename])

    def create_stratum(self, morph):
        '''Create a Baserock stratum from the ``self._inst`` directory.
        
        The directory must be filled in with all the relevant files already.
        
        '''

        # FIXME: Should put in stratum's git repo and reference here.
        filename = self.get_cached_name('stratum', '', '')
        logging.debug('Creating stratum %s at %s' % (morph.name, filename))
        self.ex.runv(['tar', '-C', self._inst, '-czf', filename, '.'])

    @property
    def _build(self):
        return self.tempdir.join('build')

    @property
    def _inst(self):
        return self.tempdir.join('inst')

    def get_cached_name(self, kind, repo, ref):
        '''Return the cached name of a binary blob, if and when it exists.'''
        abs_ref = self.get_git_commit_id(repo, ref)
        dict_key = {
            'kind': kind,
            'arch': self.arch,
            'repo': repo,
            'ref': abs_ref,
        }
        return self.cachedir.name(dict_key)

    def get_git_commit_id(self, repo, ref):
        '''Return the full SHA-1 commit id for a repo+ref.'''
        if repo and ref:
            ex = morphlib.execute.Execute(repo, self.msg)
            out = ex.runv(['git', 'rev-list', '-n1', ref])
            return out.strip()
        else:
            return ''

