# Copyright (C) 2013,2015  Codethink Limited
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
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# =*= License: GPL-2 =*=


'''A module to create, query, and manipulate Morph workspaces.'''


import os

import morphlib


class WorkspaceDirExists(morphlib.Error):

    def __init__(self, dirname):
        self.msg = (
            'can only initialize empty directory as a workspace: %s' %
            dirname)


class NotInWorkspace(morphlib.Error):

    def __init__(self, dirname):
        self.msg = (
            "Can't find the workspace directory.\n"
            "Morph must be built and deployed within the "
                "system branch checkout within the workspace directory.")


class Workspace(object):

    '''A Morph workspace.

    This class should be instantiated with the open() or create()
    functions in this module.

    '''

    def __init__(self, root_directory):
        self.root = root_directory

    def get_default_system_branch_directory_name(self, system_branch_name):
        '''Determine directory where a system branch would be checked out.

        Return the fully qualified pathname to the directory where
        a system branch would be checked out. The directory may or may
        not exist already.

        If the system branch is checked out, but into a directory of
        a different name (which is allowed), that is ignored: this method
        only computed the default name.

        '''

        return os.path.join(self.root, system_branch_name)

    def create_system_branch_directory(self,
        root_repository_url, system_branch_name):
        '''Create a directory for a system branch.

        Return a SystemBranchDirectory object that represents the
        directory. The directory must not already exist. The directory
        gets created and initialised (the .morph-system-branch/config
        file gets created and populated). The root repository of the
        system branch does NOT get checked out, the caller needs to
        do that.

        '''

        dirname = self.get_default_system_branch_directory_name(
            system_branch_name)
        sb = morphlib.sysbranchdir.create(
            dirname, root_repository_url, system_branch_name)
        return sb

    def list_system_branches(self):
        return (morphlib.sysbranchdir.open(dirname)
                for dirname in
                morphlib.util.find_leaves(self.root, '.morph-system-branch'))


def open(dirname):
    '''Open an existing workspace.

    The given directory name may be to a subdirectory of the
    workspace. This makes it easy to instantiate the Workspace
    class even when the user invokes Morph in a subdirectory.
    The workspace MUST exist already, or NotInWorkspace is
    raised.

    Return a Workspace instance.

    '''

    root = _find_root(dirname)
    if root is None:
        raise NotInWorkspace(dirname)
    return Workspace(root)


def create(dirname):
    '''Create a new workspace.

    The given directory must not be inside an existing workspace.
    The workspace directory is created, unless it already exists.  If it
    does exist, it must be empty. Otherwise WorkspaceDirExists is raised.

    '''

    root = _find_root(dirname)
    if root is not None:
        raise WorkspaceDirExists(root)

    if os.path.exists(dirname):
        if os.listdir(dirname):
            raise WorkspaceDirExists(dirname)
    else:
        os.mkdir(dirname)
    os.mkdir(os.path.join(dirname, '.morph'))
    return Workspace(dirname)


def _find_root(dirname):
    '''Find the workspace root directory at or above a given directory.'''

    dirname = os.path.normpath(os.path.abspath(dirname))
    while not os.path.isdir(os.path.join(dirname, '.morph')):
        if dirname == '/':
            return None
        dirname = os.path.dirname(dirname)
    return dirname

