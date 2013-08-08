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
import stat
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
        '''Deploy a built system image.

        Command line arguments:

        * `TYPE` is the type of deployment: to a raw disk image,
          VirtualBox, or something else. See below.

        * `SYSTEM` is the name of the system morphology to deploy.

        * `LOCATION` is where the deployed system should end up at. The
          syntax depends on the deployment type. See below.

        * `KEY=VALUE` is a configuration parameter to pass onto the
          configuration extension. See below.

        Morph can deploy a system image. The deployment mechanism is
        quite flexible, and can be extended by the user. "Deployment"
        here is quite a general concept: it covers anything where a system
        image is taken, configured, and then put somewhere where it can
        be run.

        `TYPE` specifies the exact way in which the deployment happens.
        Morph provides four deployment types:

        * `rawdisk` where Morph builds a raw disk image at `LOCATION`,
          and sets up the image with a bootloader and configuration
          so that it can be booted. Disk size is set with `DISK_SIZE`
          (see below).

        * `virtualbox-ssh` where Morph creates a VirtualBox disk image,
          and creates a new virtual machine on a remote host, accessed
          over ssh.  Disk and RAM size are set with `DISK_SIZE` and
          `RAM_SIZE` (see below).

        * `kvm`, which is similar to `virtualbox-ssh`, but uses libvirt
          and KVM instead of VirtualBox.  Disk and RAM size are set with
          `DISK_SIZE` and `RAM_SIZE` (see below).

        * `nfsboot` where Morph creates a system to be booted over
          a network

        The following `KEY=VALUE` parameters are supported for all
        deployment types:

        * `DISK_SIZE=X` to set the size of the disk image. `X`
          should use a suffix of `K`, `M`, or `G` (in upper or lower
          case) to indicate kilo-, mega-, or gigabytes. For example,
          `DISK_SIZE=100G` would create a 100 gigabyte disk image. **This
          parameter is mandatory**.

        * `RAM_SIZE=X` to set the size of virtual RAM for the virtual
          machine.  `X` is interpreted in the same was as `DISK_SIZE`,
          and defaults to `1G`.

        The `kvm` and `virtualbox-ssh` deployment types support an
        additional parameter:

        * `AUTOSTART=<VALUE>` - allowed values are `yes` and `no`
          (default)

        The syntax of the `LOCATION` depends on the deployment types. The
        deployment types provided by Morph use the following syntaxes:

        * `rawdisk`: pathname to the disk image to be created; for
          example, `/home/alice/testsystem.img`

        * `virtualbox-ssh` and `kvm`: a custom URL scheme that
          provides the target host machine (the one that runs
          VirtualBox or `kvm`), the name of the new virtual machine,
          and the location on the target host of the virtual disk
          file. The target host is accessed over ssh. For example,
          `vbox+ssh://alice@192.168.122.1/testsys/home/alice/testsys.vdi`
          or `kvm+ssh://alice@192.168.122.1/testsys/home/alice/testys.img`
          where

              * `alice@192.168.122.1` is the target as given to ssh,
                **from within the development host** (which may be
                different from the target host's normal address);

              * `testsys` is the new VM's name;

              * `/home/alice/testsys.vdi` and `/home/alice/testys.img` are
                the pathnames of the disk image files on the target host.

        For the `nfsboot` write extension,

        * LOCATION is the address of the nfsboot server. (Note this
          is just the _address_ of the trove, _not_ `user@...`, since
          `root@` will automatically be prepended to the server address.)

        * the following KEY=VALUE PAIRS are mandatory

              * NFSBOOT_CONFIGURE=yes (or any non-empty value). This
                enables the `nfsboot` configuration extension (see
                below) which MUST be used when using the `nfsboot`
                write extension.

              * HOSTNAME=<STRING> a unique identifier for that system's
                `nfs` root when it's deployed on the nfsboot server - the
                extension creates a directory with that name for the `nfs`
                root, and stores kernels by that name for the tftp server.

        * the following KEY=VALUE PAIRS are optional

              * VERSION_LABEL=<STRING> - set the name of the system
                version being deployed, when upgrading. Defaults to
                "factory".

        An example command line using `morph deploy with the nfsboot`
        type is

            morph deploy nfsboot devel-system-x86_64-generic \
            customer-trove \
            NFSBOOT_CONFIGURE=yes \
            HOSTNAME=test-deployment-1 \
            VERSION_LABEL=inital-test

        Each deployment type is implemented by a **write extension**. The
        ones provided by Morph are listed above, but users may also
        create their own by adding them in the same git repository
        and branch as the system morphology. A write extension is a
        script that does whatever is needed for the deployment. A write
        extension is passed two command line parameters: the name of an
        unpacked directory tree that contains the system files (after
        configuration, see below), and the `LOCATION` argument. Any
        additional `KEY=VALUE` arguments given to `morph deploy` are
        set as environment variables when the write extension runs.

        Regardless of the type of deployment, the image may be
        configured for a specific deployment by using **configuration
        extensions**. The extensions are listed in the system morphology
        file:

            ...
            configuration-extensions:
                - set-hostname

        The above specifies that the extension `set-hostname` is to
        be run.  Morph will run all the configuration extensions listed
        in the system morphology, and no others. (This way, configuration
        is more easily tracked in git.)

        Configuration extensions are scripts that get the unpacked
        directory tree of the system as their parameter, and do whatever
        is needed to configure the tree.

        Morph provides the following configuration extension built in:

        * `set-hostname` sets the hostname of the system to the value
          of the `HOSTNAME` variable.
        * `nfsboot` configures the system for nfsbooting. This MUST
          be used when deploying with the `nfsboot` write extension.

        Any `KEY=VALUE` parameters given to `morph deploy` are set as
        environment variables when either the configuration or the write
        extension runs.

        '''

        if len(args) < 3:
            raise cliapp.AppException(
                'Too few arguments to deploy command (see help)')

        # Raise an exception if there is not enough space in tempdir
        # / for the path and 0 for the minimum size is a no-op
        # it exists because it is complicated to check the available
        # disk space given dirs may be on the same device
        morphlib.util.check_disk_available(
            self.app.settings['tempdir'],
            self.app.settings['tempdir-min-space'],
            '/', 0)

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

        # Find system branch root repository on the local disk.
        root_repo = self.other.get_branch_config(branch_dir, 'branch.root')
        root_repo_dir = self.other.find_repository(branch_dir, root_repo)

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
        srcpool = build_command.create_source_pool(
            build_branch_root,
            build_ref,
            system_name + '.morph')
        artifact = build_command.resolve_artifacts(srcpool)

        if push:
            self.other.delete_remote_build_refs(build_repos)
            
        # Unpack the artifact (tarball) to a temporary directory.
        self.app.status(msg='Unpacking system for configuration')

        deploy_tempdir = tempfile.mkdtemp(
            dir=os.path.join(self.app.settings['tempdir'], 'deployments'))
        system_tree = tempfile.mkdtemp(dir=deploy_tempdir)

        if build_command.lac.has(artifact):
            f = build_command.lac.get(artifact)
        elif build_command.rac.has(artifact):
            f = build_command.rac.get(artifact)
        else:
            raise cliapp.AppException('Deployment failed as system is not yet'
                                      ' built.\nPlease ensure system is built'
                                      ' before deployment.')
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

        # Extensions get a private tempdir so we can more easily clean
        # up any files an extension left behind
        deploy_private_tempdir = tempfile.mkdtemp(dir=deploy_tempdir)
        env['TMPDIR'] = deploy_private_tempdir

        # Run configuration extensions.
        self.app.status(msg='Configure system')
        names = artifact.source.morphology['configuration-extensions']
        for name in names:
            self._run_extension(
                root_repo_dir,
                build_ref,
                name,
                '.configure',
                [system_tree],
                env)
        
        # Run write extension.
        self.app.status(msg='Writing to device')
        self._run_extension(
            root_repo_dir,
            build_ref,
            deployment_type,
            '.write',
            [system_tree, location],
            env)
        
        # Cleanup.
        self.app.status(msg='Cleaning up')
        shutil.rmtree(deploy_tempdir)

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
            if not self._is_executable(ext_filename):
                raise morphlib.Error(
                    'Extension not executable: %s' % ext_filename)
            delete_ext = False
        else:
            # Found it in the system morphology's repository.
            fd, ext_filename = tempfile.mkstemp()
            os.write(fd, ext)
            os.close(fd)
            os.chmod(ext_filename, 0700)
            delete_ext = True

        self.app.status(msg='Running extension %(name)s%(kind)s',
                        name=name, kind=kind)
        self.app.runcmd(
            [ext_filename] + args,
            ['sh', '-c', 'while read l; do echo `date "+%F %T"` $l; done'],
            env=env, stdout=None, stderr=None)
        
        if delete_ext:
            os.remove(ext_filename)

    def _is_executable(self, filename):
        st = os.stat(filename)
        mask = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        return (stat.S_IMODE(st.st_mode) & mask) != 0
        
    def _cat_file(self, repo_dir, ref, pathname):
        '''Retrieve contents of a file from a git repository.'''
        
        argv = ['git', 'cat-file', 'blob', '%s:%s' % (ref, pathname)]
        try:
            return self.app.runcmd(argv, cwd=repo_dir)
        except cliapp.AppException:
            return None

