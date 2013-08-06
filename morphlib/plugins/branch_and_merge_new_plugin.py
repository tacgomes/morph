# Copyright (C) 2012,2013  Codethink Limited
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
import logging
import os
import shutil

import morphlib


class SimpleBranchAndMergePlugin(cliapp.Plugin):

    '''Add subcommands for handling workspaces and system branches.'''

    def enable(self):
        self.app.add_subcommand('init', self.init, arg_synopsis='[DIR]')
        self.app.add_subcommand('workspace', self.workspace, arg_synopsis='')
        self.app.add_subcommand(
            'checkout', self.checkout, arg_synopsis='REPO BRANCH')
        self.app.add_subcommand(
            'show-system-branch', self.show_system_branch, arg_synopsis='')
        self.app.add_subcommand(
            'show-branch-root', self.show_branch_root, arg_synopsis='')

    def disable(self):
        pass

    def init(self, args):
        '''Initialize a workspace directory.

        Command line argument:

        * `DIR` is the directory to use as a workspace, and defaults to
          the current directory.

        This creates a workspace, either in the current working directory,
        or if `DIR` is given, in that directory. If the directory doesn't
        exist, it is created. If it does exist, it must be empty.

        You need to run `morph init` to initialise a workspace, or none
        of the other system branching tools will work: they all assume
        an existing workspace. Note that a workspace only exists on your
        machine, not on the git server.

        Example:

            morph init /src/workspace
            cd /src/workspace

        '''

        if not args:
            args = ['.']
        elif len(args) > 1:
            raise morphlib.Error('init must get at most one argument')

        ws = morphlib.workspace.create(args[0])
        self.app.status(msg='Initialized morph workspace', chatty=True)

    def workspace(self, args):
        '''Show the toplevel directory of the current workspace.'''

        ws = morphlib.workspace.open('.')
        self.app.output.write('%s\n' % ws.root)

    def checkout(self, args):
        '''Check out an existing system branch.

        Command line arguments:

        * `REPO` is the URL to the repository to the root repository of
          a system branch.
        * `BRANCH` is the name of the system branch.

        This will check out an existing system branch to an existing
        workspace.  You must create the workspace first. This only checks
        out the root repository, not the repositories for individual
        components. You need to use `morph edit` to check out those.

        Example:

            cd /src/workspace
            morph checkout baserock:baserock/morphs master

        '''

        if len(args) != 2:
            raise cliapp.AppException('morph checkout needs a repo and the '
                                      'name of a branch as parameters')

        root_url = args[0]
        system_branch = args[1]

        self._require_git_user_config()

        # Open the workspace first thing, so user gets a quick error if
        # we're not inside a workspace.
        ws = morphlib.workspace.open('.')

        # Make sure the root repository is in the local git repository
        # cache, and is up to date.
        lrc, rrc = morphlib.util.new_repo_caches(self.app)
        cached_repo = lrc.get_updated_repo(root_url)

        # Check the git branch exists.
        cached_repo.resolve_ref(system_branch)

        root_dir = ws.get_default_system_branch_directory_name(system_branch)

        try:
            # Create the system branch directory. This doesn't yet clone
            # the root repository there.
            sb = morphlib.sysbranchdir.create(
                root_dir, root_url, system_branch)

            gd = sb.clone_cached_repo(
                cached_repo, system_branch, system_branch)
            gd.update_submodules(self.app)
            gd.update_remotes()
        except BaseException as e:
            # Oops. Clean up.
            logging.error('Caught exception: %s' % str(e))
            logging.info('Removing half-finished branch %s' % system_branch)
            self._remove_branch_dir_safe(ws.root, root_dir)
            raise

    def show_system_branch(self, args):
        '''Show the name of the current system branch.'''

        ws = morphlib.workspace.open('.')
        sb = morphlib.sysbranchdir.open_from_within('.')
        self.app.output.write('%s\n' % sb.system_branch_name)

    def show_branch_root(self, args):
        '''Show the name of the repository holding the system morphologies.

        This would, for example, write out something like:

            /src/ws/master/baserock:baserock/morphs

        when the master branch of the `baserock:baserock/morphs`
        repository is checked out.

        '''

        ws = morphlib.workspace.open('.')
        sb = morphlib.sysbranchdir.open_from_within('.')
        self.app.output.write('%s\n' % sb.get_config('branch.root'))

    def _remove_branch_dir_safe(self, workspace_root, system_branch_root):
        # This function avoids throwing any exceptions, so it is safe to call
        # inside an 'except' block without altering the backtrace.

        def handle_error(function, path, excinfo):
            logging.warning ("Error while trying to clean up %s: %s" %
                             (path, excinfo))

        shutil.rmtree(system_branch_root, onerror=handle_error)

        # Remove parent directories that are empty too, avoiding exceptions
        parent = os.path.dirname(system_branch_root)
        while parent != os.path.abspath(workspace_root):
            if len(os.listdir(parent)) > 0 or os.path.islink(parent):
                break
            os.rmdir(parent)
            parent = os.path.dirname(parent)

    def _require_git_user_config(self):
        '''Warn if the git user.name and user.email variables are not set.'''

        keys = {
            'user.name': 'My Name',
            'user.email': 'me@example.com',
        }

        try:
            morphlib.git.check_config_set(self.app.runcmd, keys)
        except morphlib.git.ConfigNotSetException as e:
            self.app.status(
                msg="WARNING: %(message)s",
                message=str(e), error=True)

