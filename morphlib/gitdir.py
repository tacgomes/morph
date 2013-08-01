# Copyright (C) 2013  Codethink Limited
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
#
# =*= License: GPL-2 =*=


import cliapp

import morphlib


class GitDirectory(object):

    '''Represent a git working tree + .git directory.

    This class represents a directory that is the result of a
    "git clone". It includes both the .git subdirectory and
    the working tree. It is a thin abstraction, meant to make
    it easier to do certain git operations.

    '''

    def __init__(self, dirname):
        self.dirname = dirname

    def _runcmd(self, argv, **kwargs):
        '''Run a command at the root of the git directory.

        See cliapp.runcmd for arguments.

        Do NOT use this from outside the class. Add more public
        methods for specific git operations instead.

        '''

        return cliapp.runcmd(argv, cwd=self.dirname, **kwargs)

    def checkout(self, branch_name): # pragma: no cover
        '''Check out a git branch.'''
        self._runcmd(['git', 'checkout', branch_name])

    def branch(self, new_branch_name, base_ref): # pragma: no cover
        '''Create a git branch based on an existing ref.

        This does not automatically check out the branch.

        base_ref may be None, in which case the current branch is used.

        '''

        argv = ['git', 'branch', new_branch_name]
        if base_ref is not None:
            argv.append(base_ref)
        self._runcmd(argv)

    def update_remotes(self): # pragma: no cover
        '''Update remotes.'''
        self._runcmd(['git', 'remote', 'update', '--prune'])

    def update_submodules(self, app): # pragma: no cover
        '''Change .gitmodules URLs, and checkout submodules.'''
        morphlib.git.update_submodules(app, self.dirname)

    def set_config(self, key, value):
        '''Set a git repository configuration variable.

        The key must have at least one period in it: foo.bar for example,
        not just foo. The part before the first period is interpreted
        by git as a section name.

        '''

        self._runcmd(['git', 'config', key, value])

    def get_config(self, key):
        '''Return value for a git repository configuration variable.'''

        value = self._runcmd(['git', 'config', key])
        return value.strip()

    def set_remote_fetch_url(self, remote_name, url):
        '''Set the fetch URL for a remote.'''
        self._runcmd(['git', 'remote', 'set-url', remote_name, url])

    def get_remote_fetch_url(self, remote_name):
        '''Return the fetch URL for a given remote.'''
        output = self._runcmd(['git', 'remote', '-v'])
        for line in output.splitlines():
            words = line.split()
            if (len(words) == 3 and
                words[0] == remote_name and
                words[2] == '(fetch)'):
                return words[1]
        return None

    def update_remotes(self): # pragma: no cover
        '''Run "git remote update --prune".'''
        self._runcmd(['git', 'remote', 'update', '--prune'])


def init(dirname):
    '''Initialise a new git repository.'''

    gd = GitDirectory(dirname)
    gd._runcmd(['git', 'init'])
    return gd


def clone_from_cached_repo(cached_repo, dirname, ref): # pragma: no cover
    '''Clone a CachedRepo into the desired directory.

    The given ref is checked out (or git's default branch is checked out
    if ref is None).

    '''

    cached_repo.clone_checkout(ref, dirname)
    return GitDirectory(dirname)

