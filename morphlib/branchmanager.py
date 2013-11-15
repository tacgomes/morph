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


import cliapp
import collections

import morphlib


class RefCleanupError(cliapp.AppException):
    def __init__(self, primary_exception, exceptions):
        self.exceptions = exceptions
        self.ex_nr = ex_nr = len(exceptions)
        self.primary_exception = primary_exception
        cliapp.AppException.__init__(
           self, '%(ex_nr)d exceptions caught when cleaning up '\
                 'after exception: %(primary_exception)r: '\
                 '%(exceptions)r' % locals())


class LocalRefManager(object):
    '''Provide atomic update over a set of refs in a set of repositories.

    Any ref changes made with the update, add and delete methods will
    be reversed after the end of the with statement the LocalRefManager
    is used in, if an exception is raised in the aforesaid with statement.

    '''

    def __init__(self):
        self._cleanup = None

    def __enter__(self):
        self._cleanup = collections.deque()
        return self

    def __exit__(self, etype, evalue, estack):
        # No exception was raised, so no cleanup is required
        if (etype, evalue, estack) == (None, None, None):
            return
        exceptions = []
        d = self._cleanup
        while d:
            op, args = d.pop()
            try:
                op(*args)
            except Exception, e:
                exceptions.append((op, args, e))
        if exceptions:
            raise RefCleanupError(evalue, exceptions)

    def update(self, gd, ref, commit, old_commit, message=None):
        '''Update a git repository's ref, reverting it on failure.

        Use gd and the other parameters to update a ref to a new value,
        and if an execption is raised in the body of the with statement
        the LocalRefManager is used in, revert the update back to its
        old value.

        See morphlib.gitdir.update_ref for more information.

        '''

        gd.update_ref(ref, commit, old_commit, message)
        # Register a cleanup callback of setting the ref back to its old value
        self._cleanup.append((type(gd).update_ref,
                              (gd, ref, old_commit, commit,
                              message and 'Revert ' + message)))

    def add(self, gd, ref, commit, message=None):
        '''Add ref to a git repository, removing it on failure.

        Use gd and the other parameters to add a new ref to the repository,
        and if an execption is raised in the body of the with statement
        the LocalRefManager is used in, delete the ref.

        See morphlib.gitdir.add_ref for more information.

        '''

        gd.add_ref(ref, commit, message)
        # Register a cleanup callback of deleting the newly added ref.
        self._cleanup.append((type(gd).delete_ref, (gd, ref, commit,
                              message and 'Revert ' + message)))

    def delete(self, gd, ref, old_commit, message=None):
        '''Delete ref from a git repository, reinstating it on failure.

        Use gd and the other parameters to delete an existing ref from
        the repository, and if an execption is raised in the body of the
        with statement the LocalRefManager is used in, re-create the ref.

        See morphlib.gitdir.add_ref for more information.

        '''

        gd.delete_ref(ref, old_commit, message)
        # Register a cleanup callback of replacing the deleted ref.
        self._cleanup.append((type(gd).add_ref, (gd, ref, old_commit,
                              message and 'Revert ' + message)))


class RemoteRefManager(object):
    '''Provide temporary pushes to remote repositories.

    Any ref changes made with the push method will be reversed after
    the end of the with statement the RemoteRefManager is used in.

    '''

    def __init__(self):
        self._cleanup = None

    def __enter__(self):
        self._cleanup = collections.deque()
        return self

    def __exit__(self, etype, evalue, estack):
        exceptions = []
        d = self._cleanup
        while d:
            remote, refspecs = d.pop()
            try:
                remote.push(*refspecs)
            except Exception, e:
                exceptions.append((remote, refspecs, e))
        if exceptions:
            raise RefCleanupError(evalue, exceptions)

    def push(self, remote, *refspecs):
        '''Push refspecs to remote and revert on failure.

        Push the specified refspecs to the remote and reverse the change
        after the end of the block the with statement the RemoteRefManager
        is used in.

        '''

        # Calculate the refspecs required to undo the pushed changes.
        delete_specs = tuple(rs.revert() for rs in refspecs)
        result = remote.push(*refspecs)
        # Register cleanup after pushing, so that if this push fails,
        # we don't try to undo it.
        self._cleanup.append((remote, delete_specs))
        return result
