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
import gzip
import os
import shutil
import tarfile
import tempfile
import urlparse
import uuid

import morphlib

# UGLY HACK: We need to re-use some code from the branch and merge
# plugin, so we import and instantiate that plugin. This needs to
# be fixed by refactoring the codebase so the shared code is in
# morphlib, not in a plugin. However, this hack lets us re-use
# code without copying it.
import morphlib.plugins.branch_and_merge_plugin


class DeployPlugin(cliapp.Plugin):

    def enable(self):
        self.app.add_subcommand(
            'deploy', self.deploy,
            arg_synopsis='TYPE SYSTEM LOCATION [KEY=VALUE]')
        self.other = \
            morphlib.plugins.branch_and_merge_plugin.BranchAndMergePlugin()
        self.other.app = self.app

    def disable(self):
        pass

    def deploy(self, args):
        '''Deploy a built system image.'''

        if len(args) < 3:
            raise cliapp.AppException(
                'Too few arguments to deploy command (see help)')

        deployment_type = args[0]
        system_name = args[1]
        location = args[2]
        env_vars = args[3:]

        # Deduce workspace and system branch and branch root repository.
        workspace = self.other.deduce_workspace()
        branch, branch_dir = self.other.deduce_system_branch()
        branch_root = self.other.get_branch_config(branch_dir, 'branch.root')
        branch_uuid = self.other.get_branch_config(branch_dir, 'branch.uuid')

        # Generate a UUID for the build.
        build_uuid = uuid.uuid4().hex

        build_command = morphlib.buildcommand.BuildCommand(self.app)
        build_command = self.app.hookmgr.call('new-build-command',
                                              build_command)
        push = self.app.settings['push-build-branches']

        self.app.status(msg='Starting build %(uuid)s', uuid=build_uuid)

        self.app.status(msg='Collecting morphologies involved in '
                            'building %(system)s from %(branch)s',
                            system=system_name, branch=branch)

        # Get repositories of morphologies involved in building this system
        # from the current system branch.
        build_repos = self.other.get_system_build_repos(
                branch, branch_dir, branch_root, system_name)

        # Generate temporary build ref names for all these repositories.
        self.other.generate_build_ref_names(build_repos, branch_uuid)

        # Create the build refs for all these repositories and commit
        # all uncommitted changes to them, updating all references
        # to system branch refs to point to the build refs instead.
        self.other.update_build_refs(build_repos, branch, build_uuid, push)

        if push:
            self.other.push_build_refs(build_repos)
            build_branch_root = branch_root
        else:
            dirname = build_repos[branch_root]['dirname']
            build_branch_root = urlparse.urljoin('file://', dirname)

        # Run the build.
        build_ref = build_repos[branch_root]['build-ref']
        artifact = build_command.get_artifact_object(
            build_branch_root,
            build_ref,
            system_name + '.morph')

        if push:
            self.other.delete_remote_build_refs(build_repos)
            
        # Unpack the artifact (tarball) to a temporary directory.
        self.app.status(msg='Unpacking system for configuration')

        system_tree = tempfile.mkdtemp(dir=self.app.settings['tempdir'])

        if build_command.lac.has(artifact):
            f = build_command.lac.get(artifact)
        else:
            f = build_command.rac.get(artifact)
        tf = tarfile.open(fileobj=f)
        tf.extractall(path=system_tree)
        
        self.app.status(
            msg='System unpacked at %(system_tree)s',
            system_tree=system_tree)

        # Set up environment for running extensions.
        env = dict(os.environ)
        for spec in env_vars:
            name, value = spec.split('=', 1)
            if name in env:
                raise morphlib.Error(
                    '%s is already set in the enviroment' % name)
            env[name] = value

        # Run configuration extensions.
        self.app.status(msg='Configure system')
        names = artifact.source.morphology['configuration-extensions']
        for name in names:
            self._run_extension(
                branch_dir,
                build_ref,
                name,
                '.configure',
                [system_tree],
                env)
        
        # Run write extension.
        self.app.status(msg='Writing to device')
        self._run_extension(
            branch_dir,
            build_ref,
            deployment_type,
            '.write',
            [system_tree, location],
            env)
        
        # Cleanup.
        self.app.status(msg='Cleaning up')
        shutil.rmtree(system_tree)

        self.app.status(msg='Finished deployment')

    def _run_extension(self, repo_dir, ref, name, kind, args, env):
        '''Run an extension.
        
        The ``kind`` should be either ``.configure`` or ``.write``,
        depending on the kind of extension that is sought.
        
        The extension is found either in the git repository of the
        system morphology (repo, ref), or with the Morph code.
        
        '''
        
        # Look for extension in the system morphology's repository.
        ext = self._cat_file(repo_dir, ref, name + kind)
        if ext is None:
            # Not found: look for it in the Morph code.
            code_dir = os.path.dirname(morphlib.__file__)
            ext_filename = os.path.join(code_dir, 'exts', name + kind)
            if not os.path.exists(ext_filename):
                raise morphlib.Error(
                    'Could not find extension %s%s' % (name, kind))
            delete_ext = False
        else:
            # Found it in the system morphology's repository.
            fd, ext_filename = tempfile.mkstemp()
            os.write(fd, ext)
            os.close(fd)
            os.chmod(ext_filename, 0700)
            delete_ext = True

        self.app.runcmd(
            [ext_filename] + args, env=env, stdout=None, stderr=None)
        
        if delete_ext:
            os.remove(ext_filename)
        
    def _cat_file(self, repo_dir, ref, pathname):
        '''Retrieve contents of a file from a git repository.'''
        
        argv = ['git', 'cat-file', 'blob', '%s:%s' % (ref, pathname)]
        try:
            return self.app.runcmd(argv, cwd=repo_dir)
        except cliapp.AppException:
            return None

