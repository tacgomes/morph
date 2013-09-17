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


import collections
import cliapp
import glob
import os

import morphlib


class NoWorkingTreeError(cliapp.AppException):

    def __init__(self, repo):
        cliapp.AppException.__init__(
            self, 'Git directory %s has no working tree '
                  '(is bare).' % repo.dirname)


class InvalidRefError(cliapp.AppException):
    def __init__(self, repo, ref):
        cliapp.AppException.__init__(
            self, 'Git directory %s has no commit '
                  'at ref %s.' %(repo.dirname, ref))


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

    def is_currently_checked_out(self, ref): # pragma: no cover
        '''Is ref currently checked out?'''

        # Try the ref name directly first. If that fails, prepend origin/
        # to it. (FIXME: That's a kludge, and should be fixed.)
        try:
            parsed_ref = self._runcmd(['git', 'rev-parse', ref]).strip()
        except cliapp.AppException:
            parsed_ref = self._runcmd(
                ['git', 'rev-parse', 'origin/%s' % ref]).strip()
        parsed_head = self._runcmd(['git', 'rev-parse', 'HEAD']).strip()
        return parsed_ref == parsed_head

    def cat_file(self, obj_type, ref, filename): # pragma: no cover
        return self._runcmd(
            ['git', 'cat-file', obj_type, '%s:%s' % (ref, filename)])

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

    def is_bare(self):
        '''Determine whether the repository has no work tree (is bare)'''
        return self.get_config('core.bare') == 'true'

    def list_files(self, ref=None):
        '''Return an iterable of the files in the repository.

        If `ref` is specified, list files at that ref, otherwise
        use the working tree.

        If this is a bare repository and no ref is specified, raises
        an exception.

        '''
        if ref is None and self.is_bare():
            raise NoWorkingTreeError(self)
        if ref is None:
            return self._list_files_in_work_tree()
        else:
            return self._list_files_in_ref(ref)

    def _rev_parse_tree(self, ref):
        try:
            return self._runcmd(['git', 'rev-parse', '--verify',
                                 '%s^{tree}' % ref]).strip()
        except cliapp.AppException as e:
            raise InvalidRefError(self, ref)

    def _list_files_in_work_tree(self):
        for dirpath, subdirs, filenames in os.walk(self.dirname):
            if dirpath == self.dirname and '.git' in subdirs:
                subdirs.remove('.git')
            for filename in filenames:
                yield os.path.join(dirpath, filename)[len(self.dirname)+1:]

    def _list_files_in_ref(self, ref):
        tree = self._rev_parse_tree(ref)
        output = self._runcmd(['git', 'ls-tree', '--name-only', '-rz', tree])
        # ls-tree appends \0 instead of interspersing, so we need to
        # strip the trailing \0 before splitting
        paths = output.strip('\0').split('\0')
        return paths

    def read_file(self, filename, ref=None):
        if ref is None and self.is_bare():
            raise NoWorkingTreeError(self)
        if ref is None:
            with open(os.path.join(self.dirname, filename)) as f:
                return f.read()
        tree = self._rev_parse_tree(ref)
        return self.cat_file('blob', tree, filename)

    @property
    def HEAD(self):
        output = self._runcmd(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
        return output.strip()

    def _get_status(self):
        '''Runs git status and formats its output into something more useful.

        This runs git status such that unusual filenames are preserved
        and returns its output in a sequence of (status_code, to_path,
        from_path).

        from_path is None unless the status_code says there was a rename,
        in which case it is the path it was renamed from.

        Untracked and ignored changes are also included in the output,
        their status codes are '??' and '!!' respectively.

        '''
        status = self._runcmd(['git', 'status', '-z', '--ignored'])
        tokens = collections.deque(status.split('\0'))
        while True:
            tok = tokens.popleft()
            # Terminates with an empty token, since status ends with a \0
            if not tok:
                return

            code = tok[:2]
            to_path = tok[3:]
            yield code, to_path, tokens.popleft() if code[0] == 'R' else None

    def get_uncommitted_changes(self):
        for code, to_path, from_path in self._get_status():
            if code not in ('??', '!!'):
                yield code, to_path, from_path


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

