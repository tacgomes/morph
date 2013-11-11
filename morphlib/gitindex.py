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


STATUS_UNTRACKED = '??'
STATUS_IGNORED = '!!'


class GitIndex(object):
    '''An object that represents operations on the working tree.

    Index objects can be constructed with a different path to the
    index file, which can be used to construct commits without
    altering the working tree, index or HEAD.

    The file must either be a previously initialised index, or a
    non-existant file.

    Git creates a lock file and atomically alters the index by
    renaming a temporary file into place, so `index_file` must be
    in a writable directory.

    '''

    def __init__(self, gd, index_file):
        self._gd = gd
        self._index_file = index_file

    def _run_git(self, *args, **kwargs):
        if self._index_file is not None:
            kwargs['env'] = kwargs.get('env', {})
            kwargs['env']['GIT_INDEX_FILE'] = self._index_file
        return self._gd._runcmd(['git'] + list(args), **kwargs)

    def _get_status(self):
        '''Return git status output in a Python useful format

        This runs git status such that unusual filenames are preserved
        and returns its output in a sequence of (status_code, to_path,
        from_path).

        from_path is None unless the status_code says there was a
        rename, in which case it is the path it was renamed from.

        Untracked and ignored changes are also included in the output,
        their status codes are '??' and '!!' respectively.

        '''

        # git status -z will NUL terminate paths, so we don't have to
        # unescape the paths it outputs. Unfortunately each status entry
        # can have 1 or 2 paths, so extra parsing is required.
        # To handle this, we split it into NUL delimited tokens.
        # The first token of an entry is the 2 character status code,
        # a space, then the path.
        # If our status code starts with R then it's a rename, hence
        # has a second path, requiring us to pop an extra token.
        status = self._run_git('status', '-z', '--ignored')
        tokens = collections.deque(status.split('\0'))
        while True:
            tok = tokens.popleft()
            # Status output is NUL terminated rather than delimited,
            # and split is for delimited output. A side effect of this is
            # that we get an empty token as the last output. This suits
            # us fine, as it gives us a sentinel value to terminate with.
            if not tok:
                return

            # The first token of an entry is 2 character status, a space,
            # then the path
            code = tok[:2]
            to_path = tok[3:]

            # If the code starts with R then it's a rename, and
            # the next token says where the file was renamed from
            from_path = tokens.popleft() if code[0] == 'R' else None
            yield code, to_path, from_path

    def get_uncommitted_changes(self):
        for code, to_path, from_path in self._get_status():
            if code not in (STATUS_UNTRACKED, STATUS_IGNORED):
                yield code, to_path, from_path

    def set_to_tree(self, treeish):
        '''Modify the index to contain the contents of the treeish.'''
        self._run_git('read-tree', treeish)
