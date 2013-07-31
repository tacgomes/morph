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

