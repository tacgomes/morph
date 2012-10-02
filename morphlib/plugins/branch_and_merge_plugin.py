# Copyright (C) 2012  Codethink Limited
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
import copy
import glob
import json
import logging
import os
import shutil
import socket
import tempfile
import time
import urlparse
import uuid

import morphlib

class BranchAndMergePlugin(cliapp.Plugin):

    def __init__(self):
        # Start recording changes.
        self.init_changelog()

    def enable(self):
        self.app.add_subcommand('init', self.init, arg_synopsis='[DIR]')
        self.app.add_subcommand('workspace', self.workspace,
                                arg_synopsis='')
        self.app.add_subcommand('branch', self.branch,
                                arg_synopsis='REPO NEW [OLD]')
        self.app.add_subcommand('checkout', self.checkout,
                                arg_synopsis='REPO BRANCH')
        self.app.add_subcommand('show-system-branch', self.show_system_branch,
                                arg_synopsis='')
        self.app.add_subcommand('show-branch-root', self.show_branch_root,
                                arg_synopsis='')
        self.app.add_subcommand('merge', self.merge,
                                arg_synopsis='BRANCH')
        self.app.add_subcommand('edit', self.edit,
                                arg_synopsis='SYSTEM STRATUM [CHUNK]')
        self.app.add_subcommand('petrify', self.petrify)
        self.app.add_subcommand('unpetrify', self.unpetrify)
        self.app.add_subcommand('build', self.build,
                                arg_synopsis='SYSTEM')
        self.app.add_subcommand('foreach', self.foreach,
                                arg_synopsis='COMMAND')
        # This command should be hidden, once cliapp supports such a thing
        self.app.add_subcommand('merge-morphology', self.merge_morphology)

    def disable(self):
        pass

    def init_changelog(self):
        self.changelog = {}

    def log_change(self, repo, text):
        if not repo in self.changelog:
            self.changelog[repo] = []
        self.changelog[repo].append(text)

    def print_changelog(self, title, early_keys=[]):
        if self.changelog and self.app.settings['verbose']:
            msg = '\n%s:\n\n' % title
            keys = [x for x in early_keys if x in self.changelog]
            keys.extend([x for x in self.changelog if x not in early_keys])
            for key in keys:
                messages = self.changelog[key]
                msg += '  %s:\n' % key
                msg += '\n'.join(['    %s' % x for x in messages])
                msg += '\n\n'
            self.app.output.write(msg)

    @staticmethod
    def deduce_workspace():
        dirname = os.getcwd()
        while dirname != '/':
            dot_morph = os.path.join(dirname, '.morph')
            if os.path.isdir(dot_morph):
                return dirname
            dirname = os.path.dirname(dirname)
        raise cliapp.AppException("Can't find the workspace directory")

    def deduce_system_branch(self):
        # 1. Deduce the workspace. If this fails, we're not inside a workspace.
        workspace = self.deduce_workspace()

        # 2. We're in a workspace. Check if we're inside a system branch.
        #    If we are, return its name.
        dirname = os.getcwd()
        while dirname != workspace and dirname != '/':
            if os.path.isdir(os.path.join(dirname, '.morph-system-branch')):
                branch_name = self.get_branch_config(dirname, 'branch.name')
                return branch_name, dirname
            dirname = os.path.dirname(dirname)

        # 3. We're in a workspace but not inside a branch. Try to find a
        #    branch directory in the directories below the current working
        #    directory. Avoid ambiguity by only recursing deeper if there
        #    is only one subdirectory.
        for dirname in self.walk_special_directories(
                os.getcwd(), special_subdir='.morph-system-branch',
                max_subdirs=1):
            branch_name = self.get_branch_config(dirname, 'branch.name')
            return branch_name, dirname

        raise cliapp.AppException("Can't find the system branch directory")

    def find_repository(self, branch_dir, repo):
        for dirname in self.walk_special_directories(branch_dir,
                                                     special_subdir='.git'):
            original_repo = self.get_repo_config(dirname, 'morph.repository')
            if repo == original_repo:
                return dirname
        return None

    def find_system_branch(self, workspace, branch_name):
        for dirname in self.walk_special_directories(
                workspace, special_subdir='.morph-system-branch'):
            branch = self.get_branch_config(dirname, 'branch.name')
            if branch_name == branch:
                return dirname
        return None

    def set_branch_config(self, branch_dir, option, value):
        filename = os.path.join(branch_dir, '.morph-system-branch', 'config')
        self.app.runcmd(['git', 'config', '-f', filename, option, value])

    def get_branch_config(self, branch_dir, option):
        filename = os.path.join(branch_dir, '.morph-system-branch', 'config')
        value = self.app.runcmd(['git', 'config', '-f', filename, option])
        return value.strip()

    def set_repo_config(self, repo_dir, option, value):
        self.app.runcmd(['git', 'config', option, value], cwd=repo_dir)

    def get_repo_config(self, repo_dir, option):
        value = self.app.runcmd(['git', 'config', option], cwd=repo_dir)
        return value.strip()

    def get_uncommitted_changes(self, repo_dir, env={}):
        status = self.app.runcmd(['git', 'status', '--porcelain'],
                                 cwd=repo_dir, env=env)
        changes = []
        for change in status.strip().splitlines():
            xy, paths = change.strip().split(' ', 1)
            if xy != '??':
                changes.append(paths.split()[0])
        return changes

    def resolve_ref(self, repodir, ref):
        try:
            return self.app.runcmd(['git', 'show-ref', ref],
                                   cwd=repodir).split()[0]
        except:
            return None

    def resolve_reponame(self, reponame):
        '''Return the full pull URL of a reponame.'''

        resolver = morphlib.repoaliasresolver.RepoAliasResolver(
            self.app.settings['repo-alias'])
        return resolver.pull_url(reponame)

    def get_cached_repo(self, repo_name):
        '''Return CachedRepo object from the local repository cache

        Repo is cached and updated if necessary. The cache itself has a
        mechanism in place to avoid multiple updates per Morph invocation.
        '''

        self.app.status(msg='Updating git repository %s in cache' % repo_name)
        if not self.app.settings['no-git-update']:
            repo = self.lrc.cache_repo(repo_name)
            repo.update()
        else:
            repo = self.lrc.get_repo(repo_name)
        return repo

    def clone_to_directory(self, dirname, reponame, ref):
        '''Clone a repository below a directory.

        As a side effect, clone it into the local repo cache.

        '''

        # Setup.
        resolver = morphlib.repoaliasresolver.RepoAliasResolver(
            self.app.settings['repo-alias'])
        repo = self.get_cached_repo(reponame)

        # Make sure the parent directories needed for the repo dir exist.
        parent_dir = os.path.dirname(dirname)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        # Clone it from cache to target directory.
        repo.clone_checkout(ref, os.path.abspath(dirname))

        # Remember the repo name we cloned from in order to be able
        # to identify the repo again later using the same name, even
        # if the user happens to rename the directory.
        self.set_repo_config(dirname, 'morph.repository', reponame)

        # Create a UUID for the clone. We will use this for naming
        # temporary refs, e.g. for building.
        self.set_repo_config(dirname, 'morph.uuid', uuid.uuid4().hex)

        # Set the origin to point at the original repository.
        morphlib.git.set_remote(self.app.runcmd, dirname, 'origin', repo.url)

        # Add push url rewrite rule to .git/config.
        self.set_repo_config(
                dirname, 'url.%s.pushInsteadOf' % resolver.push_url(reponame),
                resolver.pull_url(reponame))

        self.app.runcmd(['git', 'remote', 'update'], cwd=dirname)

    def load_morphology(self, repo_dir, name, ref=None):
        '''Loads a morphology from a repo in a system branch

        If 'ref' is specified, the version is taken from there instead of the
        working tree. Note that you shouldn't use this to fetch files on
        branches other than the current system branch, because the remote in
        the system branch repo may be completely out of date. Use the local
        repository cache instead for this.
        '''

        if ref is None:
            filename = os.path.join(repo_dir, '%s.morph' % name)
            with open(filename) as f:
                text = f.read()
        else:
            if not morphlib.git.is_valid_sha1(ref):
                ref = morphlib.git.rev_parse(self.app.runcmd, repo_dir, ref)
            try:
                text = self.app.runcmd(['git', 'cat-file', 'blob',
                                       '%s:%s.morph' % (ref, name)],
                                       cwd=repo_dir)
            except cliapp.AppException as e:
                msg = '%s.morph was not found in %s' % (name, repo_dir)
                if ref is not None:
                    msg += ' at ref %s' % ref
                raise cliapp.AppException(msg)
        morphology = morphlib.morph2.Morphology(text)
        return morphology

    def reset_work_tree_safe(self, repo_dir):
        # This function avoids throwing any exceptions, so it is safe to call
        # inside an 'except' block without altering the backtrace.

        command = 'git', 'reset', '--hard'
        status, output, error = self.app.runcmd_unchecked(command,
                                                          cwd=repo_dir)
        if status != 0:
            logging.warning ("Warning: error while trying to clean up %s: %s" %
                             (repo_dir, error))

    @staticmethod
    def save_morphology(repo_dir, name, morphology):
        if not name.endswith('.morph'):
            name = '%s.morph' % name
        if os.path.isabs(name):
            filename = name
        else:
            filename = os.path.join(repo_dir, name)
        filename = os.path.join(repo_dir, '%s' % name)
        with morphlib.savefile.SaveFile(filename, 'w') as f:
            morphology.write_to_file(f)

        if name != morphology['name']:
            logging.warning('%s: morphology "name" should match filename' %
                            filename)

    @staticmethod
    def get_edit_info(morphology_name, morphology, name, collection='strata'):
        try:
            return morphology.lookup_child_by_name(name)
        except KeyError:
            if collection is 'strata':
                raise cliapp.AppException(
                        'Stratum "%s" not found in system "%s"' %
                        (name, morphology_name))
            else:
                raise cliapp.AppException(
                        'Chunk "%s" not found in stratum "%s"' %
                        (name, morphology_name))

    @staticmethod
    def convert_uri_to_path(uri):
        parts = urlparse.urlparse(uri)

        # If the URI path is relative, assume it is an aliased repo (e.g.
        # baserock:morphs). Otherwise assume it is a full URI where we need
        # to strip off the scheme and .git suffix.
        if not os.path.isabs(parts.path):
            return uri
        else:
            path = parts.netloc
            if parts.path.endswith('.git'):
                path = os.path.join(path, parts.path[1:-len('.git')])
            else:
                path = os.path.join(path, parts.path[1:])
            return path

    @staticmethod
    def remove_branch_dir_safe(workspace, branch):
        # This function avoids throwing any exceptions, so it is safe to call
        # inside an 'except' block without altering the backtrace.

        def handle_error(function, path, excinfo):
            logging.warning ("Warning: error while trying to clean up %s: %s" %
                             (path, excinfo))

        branch_dir = os.path.join(workspace, branch)
        shutil.rmtree(branch_dir, onerror=handle_error)

        # Remove parent directories that are empty too, avoiding exceptions
        parent = os.path.dirname(branch_dir)
        while parent != os.path.abspath(workspace):
            if len(os.listdir(parent)) > 0 or os.path.islink(parent):
                break
            os.rmdir(parent)
            parent = os.path.dirname(parent)

    @staticmethod
    def walk_special_directories(root_dir, special_subdir=None, max_subdirs=0):
        assert(special_subdir is not None)
        assert(max_subdirs >= 0)

        visited = set()
        for dirname, subdirs, files in os.walk(root_dir, followlinks=True):
            # Avoid infinite recursion due to symlinks.
            if dirname in visited:
                subdirs[:] = []
                continue
            visited.add(dirname)

            # Check if the current directory has the special subdirectory.
            if special_subdir in subdirs:
                yield dirname

            # Do not recurse into hidden directories.
            subdirs[:] = [x for x in subdirs if not x.startswith('.')]

            # Do not recurse if there is more than the maximum number of
            # subdirectories allowed.
            if max_subdirs > 0 and len(subdirs) > max_subdirs:
                break

    def init(self, args):
        '''Initialize a workspace directory.'''

        if not args:
            args = ['.']
        elif len(args) > 1:
            raise cliapp.AppException('init must get at most one argument')

        dirname = args[0]

        # verify the workspace is empty (and thus, can be used) or
        # create it if it doesn't exist yet
        if os.path.exists(dirname):
            if os.listdir(dirname) != []:
                raise cliapp.AppException('can only initialize empty '
                                          'directory as a workspace: %s' %
                                          dirname)
        else:
            try:
                os.makedirs(dirname)
            except:
                raise cliapp.AppException('failed to create workspace: %s' %
                                          dirname)

        os.mkdir(os.path.join(dirname, '.morph'))
        self.app.status(msg='Initialized morph workspace', chatty=True)

    def workspace(self, args):
        '''Find morph workspace directory from current working directory.'''

        self.app.output.write('%s\n' % self.deduce_workspace())

    def branch(self, args):
        '''Branch the whole system.'''

        if len(args) not in [2, 3]:
            raise cliapp.AppException('morph branch needs name of branch '
                                      'as parameter')

        repo = args[0]
        new_branch = args[1]
        commit = 'master' if len(args) == 2 else args[2]

        # Create the system branch directory.
        workspace = self.deduce_workspace()
        branch_dir = os.path.join(workspace, new_branch)
        os.makedirs(branch_dir)
        self.lrc, self.rrc = morphlib.util.new_repo_caches(self.app)

        try:
            # Create a .morph-system-branch directory to clearly identify
            # this directory as a morph system branch.
            os.mkdir(os.path.join(branch_dir, '.morph-system-branch'))

            # Remember the system branch name and the repository we branched
            # off from initially.
            self.set_branch_config(branch_dir, 'branch.name', new_branch)
            self.set_branch_config(branch_dir, 'branch.root', repo)

            # Generate a UUID for the branch. We will use this for naming
            # temporary refs, e.g. building.
            self.set_branch_config(branch_dir, 'branch.uuid', uuid.uuid4().hex)

            # Clone into system branch directory.
            repo_dir = os.path.join(branch_dir, self.convert_uri_to_path(repo))
            self.clone_to_directory(repo_dir, repo, commit)

            # Check if branch already exists locally or in a remote
            if self.resolve_ref(repo_dir, new_branch) is not None:
                raise cliapp.AppException('branch %s already exists in '
                                          'repository %s' % (new_branch, repo))

            # Create a new branch in the local morphs repository.
            self.app.runcmd(['git', 'checkout', '-b', new_branch, commit],
                            cwd=repo_dir)
        except:
            self.remove_branch_dir_safe(workspace, new_branch)
            raise

    def checkout(self, args):
        '''Check out an existing system branch.'''

        if len(args) != 2:
            raise cliapp.AppException('morph checkout needs a repo and the '
                                      'name of a branch as parameters')

        repo = args[0]
        system_branch = args[1]

        # Create the system branch directory.
        workspace = self.deduce_workspace()
        branch_dir = os.path.join(workspace, system_branch)
        os.makedirs(branch_dir)
        self.lrc, self.rrc = morphlib.util.new_repo_caches(self.app)

        try:
            # Create a .morph-system-branch directory to clearly identify
            # this directory as a morph system branch.
            os.mkdir(os.path.join(branch_dir, '.morph-system-branch'))

            # Remember the system branch name and the repository we
            # branched off from.
            self.set_branch_config(branch_dir, 'branch.name', system_branch)
            self.set_branch_config(branch_dir, 'branch.root', repo)

            # Generate a UUID for the branch.
            self.set_branch_config(branch_dir, 'branch.uuid', uuid.uuid4().hex)

            # Clone into system branch directory.
            repo_dir = os.path.join(branch_dir, self.convert_uri_to_path(repo))
            self.clone_to_directory(repo_dir, repo, system_branch)
        except:
            self.remove_branch_dir_safe(workspace, system_branch)
            raise

    def show_system_branch(self, args):
        '''Print name of current system branch.'''

        branch, dirname = self.deduce_system_branch()
        self.app.output.write('%s\n' % branch)

    def show_branch_root(self, args):
        '''Print name of the repository that was branched off from.'''

        workspace = self.deduce_workspace()
        system_branch, branch_dir = self.deduce_system_branch()
        branch_root = self.get_branch_config(branch_dir, 'branch.root')
        self.app.output.write('%s\n' % branch_root)

    def checkout_repository(self, branch_dir, repo, ref, parent_ref=None):
        '''Make a chunk or stratum repository available for a system branch

        We ensure the 'system_branch' ref within 'repo' is checked out,
        creating it from 'parent_ref' if required.

        The function aims for permissiveness, so users can try to fix any
        weirdness they have caused in the repos with another call to 'morph
        edit'.

        '''

        parent_ref = parent_ref or ref

        repo_dir = self.find_repository(branch_dir, repo)
        if repo_dir is None:
            repo_url = self.resolve_reponame(repo)
            repo_dir = os.path.join(branch_dir, self.convert_uri_to_path(repo))
            self.clone_to_directory(repo_dir, repo, parent_ref)

        if self.resolve_ref(repo_dir, ref) is None:
            self.log_change(repo, 'branch "%s" created from "%s"' %
                            (ref, parent_ref))
            command = ['git', 'checkout', '-b', ref]
        else:
            # git copes even if the system_branch ref is already checked out
            command = ['git', 'checkout', ref]

        status, output, error = self.app.runcmd_unchecked(
            command, cwd=repo_dir)
        if status != 0:
            raise cliapp.AppException('Command failed: %s in repo %s\n%s' %
                                      (' '.join(command), repo, error))
        return repo_dir

    def edit_stratum(self, system_branch, branch_dir, branch_root,
                     branch_root_dir, stratum):
        if stratum['repo'] == branch_root:
            stratum_repo_dir = branch_root_dir
            if stratum['ref'] != system_branch:
                # We need to bring the morphology forwards from its ref to the
                # current HEAD
                repo = self.lrc.get_repo(branch_root)
                stratum_morphology = repo.load_morphology(
                    stratum['ref'], stratum['morph'])
                self.save_morphology(branch_root_dir,
                    stratum['morph'], stratum_morphology)
                self.log_change(
                    stratum['repo'],
                    '"%s" copied from "%s" to "%s"' %
                    (stratum['morph'], stratum['ref'], system_branch))
        else:
            # Make sure the stratum repository is available
            stratum_repo_dir = self.checkout_repository(
                branch_dir, stratum['repo'], system_branch,
                parent_ref=stratum['ref'])

        stratum['ref'] = system_branch
        return stratum_repo_dir

    def edit_chunk(self, system_branch, branch_dir, stratum_repo_dir, chunk):
        if 'unpetrify-ref' in chunk:
            chunk['ref'] = chunk['unpetrify-ref']
            del chunk['unpetrify-ref']

        # Make the chunk repository and the ref available locally.
        chunk_repo_dir = self.checkout_repository(
                branch_dir, chunk['repo'], system_branch,
                parent_ref=chunk['ref'])

        # Check if we need to update anything at all.
        if chunk['ref'] != system_branch:
            # Update the reference to the chunk in the stratum morphology.
            chunk['ref'] = system_branch

    def edit(self, args):
        '''Edit a component in a system branch.'''

        if len(args) not in (2, 3):
            raise cliapp.AppException(
                'morph edit must either get a system and a stratum '
                'or a system, a stratum and a chunk as arguments')

        workspace = self.deduce_workspace()
        system_branch, branch_dir = self.deduce_system_branch()

        # Find out which repository we branched off from.
        branch_root = self.get_branch_config(branch_dir, 'branch.root')
        branch_root_dir = self.find_repository(branch_dir, branch_root)

        system_name = args[0]
        stratum_name = args[1]
        chunk_name = args[2] if len(args) > 2 else None

        self.lrc, self.rrc = morphlib.util.new_repo_caches(self.app)

        # Load the system morphology and find out which repo and ref
        # we need to edit the stratum.
        system_morphology = self.load_morphology(branch_root_dir, system_name)
        stratum = self.get_edit_info(system_name, system_morphology,
                                     stratum_name, collection='strata')
        stratum_repo_dir = self.edit_stratum(
            system_branch, branch_dir, branch_root, branch_root_dir, stratum)
        self.save_morphology(branch_root_dir, system_name,
                             system_morphology)
        self.log_change(branch_root,
                        '"%s" now includes "%s" from "%s"' %
                        (system_name, stratum_name, system_branch))

        if chunk_name:
            # Load the stratum morphology and find out which repo and ref
            # we need to edit the chunk.
            stratum_morphology = self.load_morphology(stratum_repo_dir,
                                                      stratum_name)
            chunk = self.get_edit_info(stratum_name, stratum_morphology,
                                       chunk_name, collection='chunks')
            self.edit_chunk(system_branch, branch_dir, stratum_repo_dir, chunk)
            self.save_morphology(stratum_repo_dir, stratum_name,
                                 stratum_morphology)
            self.log_change(stratum['repo'],
                            '"%s" now includes "%s" from "%s"' %
                            (stratum_name, chunk_name, system_branch))

        self.print_changelog('The following changes were made but have not '
                             'been comitted')

    def petrify(self, args):
        '''Convert all chunk refs in a branch to be fixed SHA1s

        This allows the developer to work on a feature in isolation, without
        changes from upstream breaking the world under their feet.

        Strata refs are not petrified, because they must all be edited to set
        the new chunk refs, which requires branching them all for the current
        branch - so they will not be updated outside of the user's control in
        any case.

        '''

        if len(args) != 0:
            raise cliapp.AppException('morph petrify takes no arguments')

        workspace = self.deduce_workspace()
        branch, branch_path = self.deduce_system_branch()
        root_repo = self.get_branch_config(branch_path, 'branch.root')
        root_repo_dir = self.find_repository(branch_path, root_repo)

        self.lrc, self.rrc = morphlib.util.new_repo_caches(self.app)

        for f in glob.glob(os.path.join(root_repo_dir, '*.morph')):
            name = os.path.basename(f)[:-len('.morph')]
            morphology = self.load_morphology(root_repo_dir, name)
            if morphology['kind'] != 'system':
                continue

            for stratum_info in morphology['strata']:
                repo_dir = self.edit_stratum(
                    branch, branch_path, root_repo, root_repo_dir,
                    stratum_info)

                stratum = self.load_morphology(repo_dir, stratum_info['morph'])

                for chunk_info in stratum['chunks']:
                    if 'unpetrify-ref' not in chunk_info:
                        commit_sha1, tree_sha1 = self.app.resolve_ref(
                            self.lrc, self.rrc, chunk_info['repo'],
                            chunk_info['ref'],
                            update=not self.app.settings['no-git-update'])
                        chunk_info['unpetrify-ref'] = chunk_info['ref']
                        chunk_info['ref'] = commit_sha1
                self.save_morphology(repo_dir, stratum_info['morph'], stratum)

            self.save_morphology(root_repo_dir, name, morphology)

        self.print_changelog('The following changes were made but have not '
                             'been comitted')

    def unpetrify(self, args):
        '''Reverse the process of petrification

        Unpetrifies all chunk refs in a branch that were previously petrified.
        Makes no attempt to 'unedit' strata that were branched solely so they
        could be petrified.

        If a branch is petrified and then branched from, the child branch can
        be unpetrified independently of the parent.

        '''

        if len(args) != 0:
            raise cliapp.AppException('morph unpetrify takes no arguments')

        self.lrc, self.rrc = morphlib.util.new_repo_caches(self.app)

        workspace = self.deduce_workspace()
        branch, branch_path = self.deduce_system_branch()
        root_repo = self.get_branch_config(branch_path, 'branch.root')
        root_repo_dir = self.find_repository(branch_path, root_repo)

        for f in glob.glob(os.path.join(root_repo_dir, '*.morph')):
            name = os.path.basename(f)[:-len('.morph')]
            morphology = self.load_morphology(root_repo_dir, name)
            if morphology['kind'] != 'system':
                continue

            for stratum_info in morphology['strata']:
                repo_dir = self.edit_stratum(
                    branch, branch_path, root_repo, root_repo_dir,
                    stratum_info)

                stratum = self.load_morphology(repo_dir, stratum_info['morph'])

                for chunk_info in stratum['chunks']:
                    if 'unpetrify-ref' in chunk_info:
                        chunk_info['ref'] = chunk_info['unpetrify-ref']
                        del chunk_info['unpetrify-ref']
                self.save_morphology(repo_dir, stratum_info['morph'], stratum)

            self.save_morphology(root_repo_dir, name, morphology)

        self.print_changelog('The following changes were made but have not '
                             'been comitted')

    def configure_merge_driver(self, repo_dir):
        self.set_repo_config(repo_dir, 'merge.morph.name',
            'Morphology merge driver')
        self.set_repo_config(repo_dir, 'merge.morph.driver',
            '%s merge-morphology $MORPH_FROM_BRANCH $MORPH_TO_BRANCH '
            '%%O %%A %%B' % self.app.__file__)

    MERGE_ATTRIBUTE = '*.morph\tmerge=morph\n'

    def enable_merge_driver(self, repo_dir):
        attributes_file = os.path.join(repo_dir, ".git", "info", "attributes")
        with open(attributes_file, 'a') as f:
            f.write(self.MERGE_ATTRIBUTE)

    def disable_merge_driver(self, repo_dir):
        attributes_file = os.path.join(repo_dir, ".git", "info", "attributes")
        with open(attributes_file, 'r') as f:
            attributes = f.read()
        if attributes == self.MERGE_ATTRIBUTE:
            os.unlink(attributes_file)
        elif attributes.endswith(self.MERGE_ATTRIBUTE):
            with morphlib.savefile.SaveFile(attributes_file, 'w') as f:
                f.write(attributes[:-len(self.MERGE_ATTRIBUTE)])

    def merge_repo(self, dirty_repos, failed_repos,
                   from_branch_dir, from_repo, from_ref,
                   to_branch_dir, to_repo, to_ref):
        '''Merge changes for a system branch in a specific repository

        This done using a standard 'git pull', with a custom merge driver to
        handle the .morph files.

        The merge driver is only invoked when there is a three-way merge
        conflict on a file. If the file has changed in the FROM branch but not
        in the TO branch (relative to the base version) git will choose the
        FROM version without considering its contents.

        Since git may automatically update morphologies in TO to use the refs
        out of FROM, the merge driver does the same, and we then reset them
        back and write the morphologies out again after recursively merging
        the components. It's important that we disable the merge driver again
        after the pull, or we risk confusing later users of the same repo who
        do a manual git merge.

        '''

        if to_repo in failed_repos:
            return None

        from_repo_dir = self.find_repository(from_branch_dir, from_repo)
        to_repo_dir = self.checkout_repository(to_branch_dir, to_repo, to_ref)

        if to_repo_dir in dirty_repos:
            return to_repo_dir
        dirty_repos.add(to_repo_dir)

        if self.get_uncommitted_changes(from_repo_dir) != []:
            raise cliapp.AppException('repository %s has uncommitted '
                                      'changes' % from_repo)
        if self.get_uncommitted_changes(to_repo_dir) != []:
            raise cliapp.AppException('repository %s has uncommitted '
                                      'changes' % to_repo)

        self.configure_merge_driver(to_repo_dir)
        self.enable_merge_driver(to_repo_dir)
        env = dict(os.environ)
        env['MORPH_FROM_BRANCH'] = from_ref
        env['MORPH_TO_BRANCH'] = to_ref
        # ':' in pathnames confuses git, so we have to pass it a URL
        from_url = urlparse.urljoin('file://', from_repo_dir)
        status, output, error = self.app.runcmd_unchecked(
            ['git', 'pull', '--quiet', '--no-commit', '--no-ff',
             from_url, from_ref], cwd=to_repo_dir, env=env)
        self.disable_merge_driver(to_repo_dir)

        if status != 0:
            self.app.output.write(
                'Merge errors encountered in %s, branch %s:\n%s'
                % (to_repo, to_ref, output))

        if status != 0:
            self.app.output.write('\n')
            failed_repos.add(to_repo)
            return None
        return to_repo_dir

    def merge(self, args):
        '''Pull and merge changes from a system branch into the current one.'''

        if len(args) != 1:
            raise cliapp.AppException('morph merge requires a system branch '
                                      'name as its argument')

        self.lrc, self.rrc = morphlib.util.new_repo_caches(self.app)
        workspace = self.deduce_workspace()
        from_branch = args[0]
        from_branch_dir = self.find_system_branch(workspace, from_branch)
        to_branch, to_branch_dir = self.deduce_system_branch()
        if from_branch_dir is None:
            raise cliapp.AppException('branch %s must be checked out before '
                                      'it can be merged' % from_branch)

        root_repo = self.get_branch_config(from_branch_dir, 'branch.root')
        other_root_repo = self.get_branch_config(to_branch_dir, 'branch.root')
        if root_repo != other_root_repo:
            raise cliapp.AppException('branches do not share a root '
                                      'repository : %s vs %s' %
                                      (root_repo, other_root_repo))

        def merge_chunk(old_ci, ci):
            self.merge_repo(
                dirty_repo_dirs, failed_repos,
                from_branch_dir, old_ci['repo'], from_branch,
                to_branch_dir, ci['repo'], ci['ref'])

        def merge_stratum(old_si, si):
            to_repo_dir = self.merge_repo(
                dirty_repo_dirs, failed_repos,
                from_branch_dir, old_si['repo'], from_branch,
                to_branch_dir, si['repo'], si['ref'])
            if to_repo_dir is None:
                return

            old_stratum, stratum = self.load_morphology_pair(
                to_repo_dir, si['repo'], old_si['ref'], si['morph'])
            changed = False
            edited_chunks = [ci for ci in stratum['chunks']
                             if ci['ref'] == from_branch]
            for ci in edited_chunks:
                for old_ci in old_stratum['chunks']:
                    if old_ci['repo'] == ci['repo']:
                        break
                else:
                    raise cliapp.AppException(
                        'chunk %s was added within this branch and '
                        'subsequently edited. This is not yet supported: '
                        'refusing to merge.' % ci['name'])
                changed = True
                ci['ref'] = old_ci['ref']
                merge_chunk(old_ci, ci)
            if changed:
                self.save_morphology(to_repo_dir, si['morph'], stratum)
                self.app.runcmd(['git', 'add', si['morph'] + '.morph'],
                                cwd=to_repo_dir)

        def merge_system(name):
            old_morphology, morphology = self.load_morphology_pair(
                to_root_dir, roo, to_branch, name)

            if morphology['kind'] != 'system':
                return

            changed = False
            edited_strata = [si for si in morphology['strata']
                             if si['ref'] == from_branch]
            for si in edited_strata:
                for old_si in old_morphology['strata']:
                    # We make no attempt at rename / move detection
                    if old_si['morph'] == si['morph'] \
                            and old_si['repo'] == si['repo']:
                        break
                else:
                    raise cliapp.AppException(
                        'stratum %s was added within this branch and '
                        'subsequently edited. This is not yet supported: '
                        'refusing to merge.' % si['morph'])
                changed = True
                si['ref'] = old_si['ref']
                merge_stratum(old_si, si)
            if changed:
                self.save_morphology(to_root_dir, name, morphology)
                self.app.runcmd(['git', 'add', f], cwd=to_root_dir)

        dirty_repo_dirs = set()
        failed_repos = set()

        # NEEDS FIXIN!
        return

        try:
            to_root_dir = self.merge_repo(
                dirty_repo_dirs, failed_repos,
                from_branch_dir, root_repo, from_branch,
                to_branch_dir, root_repo, to_branch)
            if to_root_dir is None:
                raise cliapp.AppException(
                    'Merging failed in %s: please \'git merge\' the latest %s '
                    'into %s in the \'%s\' system branch.' %
                    (root_repo, to_branch, from_branch, from_branch))

            for f in glob.glob(os.path.join(to_root_dir, '*.morph')):
                name = os.path.basename(f)[:-len('.morph')]
                merge_system(name)

            if len(failed_repos) > 0:
                raise cliapp.AppException(
                    'merge errors were encountered in the following %s:\n\n'
                    '\t%s\n\nPlease manually merge the target ref into %s in '
                    'each case in the %s system branch, and then repeat the '
                    'system branch merge.' %
                    ('repository' if len(failed_repos)==1 else 'repositories',
                     '\n\t'.join(failed_repos), from_branch, from_branch))

            for repo_dir in dirty_repo_dirs:
                # Repo will often turn out to not be dirty: if the changes we
                # merged only updated refs to the system branch, we will have
                # changed them back again so that the index will now be empty.
                if morphlib.git.index_has_changes(self.app.runcmd, repo_dir):
                    msg = "Merge system branch '%s'" % from_branch
                    self.app.runcmd(['git', 'commit', '--all', '-m%s' % msg],
                                    cwd=repo_dir)

            self.app.status(msg="Merge successful")
        except:
            for repo_dir in dirty_repo_dirs:
                self.reset_work_tree_safe(repo_dir)
            raise

    def merge_morphology_contents(self, from_branch, from_morph, to_morph):
        if from_morph['kind'] != to_morph['kind'] or \
           from_morph['name'] != to_morph['name']:
            raise cliapp.AppException('mismatch in name or kind')

        pairs = []
        if to_morph['kind'] == 'system':
            pairs = zip(from_morph['strata'], to_morph['strata'])
        elif to_morph['kind'] == 'stratum':
            pairs = zip(from_morph['chunks'], to_morph['chunks'])

        for from_child, to_child in pairs:
            if from_child['morph'] != to_child['morph'] or \
               from_child['repo'] != to_child['repo']:
                continue

            # 'morph merge' has two stages, of which this is the first. In the
            # second stage we iterate each component whose 'ref' points to
            # 'from_branch', merge inside its repository, and then update the
            # morphology again to point at the merged ref in that repository.
            # That is why we apparently merge the 'ref' field backwards here.
            if from_child['ref'] == from_branch:
                to_child['ref'] = from_branch

    def merge_morphology(self, args):
        '''Automatically merge changes between two conflicting morphologies.

        Normally executed as a git merge driver.

        In the future, this function can be expanded to resolve changes in
        field ordering.

        '''

        if len(args) != 5:
            raise cliapp.AppException('this command is not meant to be run '
                                      'manually.')

        from_branch = args[0]
        to_branch = args[1]
        base_file = args[2]
        to_file = args[3]     # local
        from_file = args[4]   # remote

        with open(from_file) as f:
            from_morph = morphlib.morph2.Morphology(f.read())
        with open(to_file) as f:
            to_morph = morphlib.morph2.Morphology(f.read())

        self.merge_morphology_contents(from_branch, from_morph, to_morph)

        # git merge gives us temporary files which we can overwrite with our
        # resolution
        with morphlib.savefile.SaveFile(to_file, 'w') as f:
            to_morph.write_to_file(f)

        # Leave the rest of the merging to git for now.
        status, output, error = self.app.runcmd_unchecked(
            ['git', 'merge-file', '-LHEAD', '-LBASE', '-L%s' % from_branch,
             to_file, base_file, from_file])
        if status != 0:
            raise cliapp.AppException('Morph did not resolve all conflicts')

    def build(self, args):
        if len(args) != 1:
            raise cliapp.AppException('morph build expects exactly one '
                                      'parameter: the system to build')

        system_name = args[0]

        # Deduce workspace and system branch and branch root repository.
        workspace = self.deduce_workspace()
        branch, branch_dir = self.deduce_system_branch()
        branch_root = self.get_branch_config(branch_dir, 'branch.root')
        branch_uuid = self.get_branch_config(branch_dir, 'branch.uuid')

        # Generate a UUID for the build.
        build_uuid = uuid.uuid4().hex

        self.app.status(msg='Starting build %(uuid)s', uuid=build_uuid)

        self.app.status(msg='Collecting morphologies involved in '
                            'building %(system)s from %(branch)s',
                            system=system_name, branch=branch)

        # Get repositories of morphologies involved in building this system
        # from the current system branch.
        build_repos = self.get_system_build_repos(
                branch, branch_dir, branch_root, system_name)

        # Generate temporary build ref names for all these repositories.
        self.generate_build_ref_names(build_repos, branch_uuid)

        # Create the build refs for all these repositories and commit
        # all uncommitted changes to them, updating all references
        # to system branch refs to point to the build refs instead.
        self.update_build_refs(build_repos, branch, build_uuid)

        # Push the temporary build refs.
        self.push_build_refs(build_repos)

        # Run the build.
        build_command = morphlib.buildcommand.BuildCommand(self.app)
        build_command = self.app.hookmgr.call('new-build-command',
                                              build_command)
        build_command.build([branch_root,
                             build_repos[branch_root]['build-ref'],
                             system_name])

        # Delete the temporary refs on the server.
        self.delete_remote_build_refs(build_repos)

        self.app.status(msg='Finished build %(uuid)s', uuid=build_uuid)

    def get_system_build_repos(self, system_branch, branch_dir,
                               branch_root, system_name):
        build_repos = {}

        def prepare_repo_info(repo, dirname):
            build_repos[repo] = {
                'dirname': dirname,
                'systems': [],
                'strata': [],
                'chunks': []
            }

        def add_morphology_info(info, category):
            repo = info['repo']
            if repo in build_repos:
                repo_dir = build_repos[repo]['dirname']
            else:
                repo_dir = self.find_repository(branch_dir, repo)
            if repo_dir:
                if not repo in build_repos:
                    prepare_repo_info(repo, repo_dir)
                build_repos[repo][category].append(info['morph'])
            return repo_dir

        # Add repository and morphology of the system.
        branch_root_dir = self.find_repository(branch_dir, branch_root)
        prepare_repo_info(branch_root, branch_root_dir)
        build_repos[branch_root]['systems'].append(system_name)

        # Traverse and add repositories and morphologies involved in
        # building this system from the system branch.
        system_morphology = self.load_morphology(branch_root_dir, system_name)
        for info in system_morphology['strata']:
            if info['ref'] == system_branch:
                repo_dir = add_morphology_info(info, 'strata')
                if repo_dir:
                    stratum_morphology = self.load_morphology(
                            repo_dir, info['morph'])
                    for info in stratum_morphology['chunks']:
                        if info['ref'] == system_branch:
                            add_morphology_info(info, 'chunks')

        return build_repos

    def inject_build_refs(self, morphology, build_repos):
        # Starting from a system or stratum morphology, update all ref
        # pointers of strata or chunks involved in a system build (represented
        # by build_repos) to point to temporary build refs of the repos
        # involved in the system build.
        def inject_build_ref(info):
            if info['repo'] in build_repos and (
                    info['morph'] in build_repos[info['repo']]['strata'] or
                    info['morph'] in build_repos[info['repo']]['chunks']):
                info['ref'] = build_repos[info['repo']]['build-ref']
        if morphology['kind'] == 'system':
            for info in morphology['strata']:
                inject_build_ref(info)
        elif morphology['kind'] == 'stratum':
            for info in morphology['chunks']:
                inject_build_ref(info)

    def generate_build_ref_names(self, build_repos, branch_uuid):
        for repo, info in build_repos.iteritems():
            repo_dir = info['dirname']
            repo_uuid = self.get_repo_config(repo_dir, 'morph.uuid')
            build_ref = os.path.join(self.app.settings['build-ref-prefix'],
                                     branch_uuid, repo_uuid)
            info['build-ref'] = build_ref

    def update_build_refs(self, build_repos, system_branch, build_uuid):
        # Define the committer.
        committer_name = 'Morph (on behalf of %s)' % \
            (morphlib.git.get_user_name(self.app.runcmd))
        committer_email = '%s@%s' % \
            (os.environ.get('LOGNAME'), socket.gethostname())

        for repo, info in build_repos.iteritems():
            repo_dir = info['dirname']
            build_ref = info['build-ref']

            self.app.status(msg='%(repo)s: Creating build branch', repo=repo)

            # Obtain parent SHA1 for the temporary ref tree to be committed.
            # This will either be the current commit of the temporary ref or
            # HEAD in case the temporary ref does not exist yet.
            parent_sha1 = self.resolve_ref(repo_dir, build_ref)
            if not parent_sha1:
                parent_sha1 = self.resolve_ref(repo_dir, system_branch)

            # Prepare an environment with our internal index file.
            # This index file allows us to commit changes to a tree without
            # git noticing any change in working tree or its own index.
            env = dict(os.environ)
            env['GIT_INDEX_FILE'] = os.path.join(
                    repo_dir, '.git', 'morph-index')
            env['GIT_COMMITTER_NAME'] = committer_name
            env['GIT_COMMITTER_EMAIL'] = committer_email

            # Read tree from parent or current HEAD into the morph index.
            self.app.runcmd(['git', 'read-tree', parent_sha1],
                            cwd=repo_dir, env=env)

            self.app.status(msg='%(repo)s: Adding uncommited changes to '
                                'build branch', repo=repo)

            # Add all local, uncommitted changes to our internal index.
            changed_files = self.get_uncommitted_changes(repo_dir, env)
            self.app.runcmd(['git', 'add'] + changed_files,
                            cwd=repo_dir, env=env)

            self.app.status(msg='%(repo)s: Update morphologies to use '
                                'build branch instead of "%(branch)s"',
                            repo=repo, branch=system_branch)

            # Update all references to the system branches of strata
            # and chunks to point to the temporary refs, which is needed
            # for building.
            filenames = info['systems'] + info['strata']
            for filename in filenames:
                # Inject temporary refs in the right places in each morphology.
                morphology = self.load_morphology(repo_dir, filename)
                self.inject_build_refs(morphology, build_repos)
                handle, tmpfile = tempfile.mkstemp(suffix='.morph')
                self.save_morphology(repo_dir, tmpfile, morphology)

                morphology_sha1 = self.app.runcmd(
                        ['git', 'hash-object', '-t', 'blob', '-w', tmpfile],
                        cwd=repo_dir, env=env)

                self.app.runcmd(
                        ['git', 'update-index', '--cacheinfo',
                         '100644', morphology_sha1, '%s.morph' % filename],
                        cwd=repo_dir, env=env)

                # Remove the temporary morphology file.
                os.remove(tmpfile)

            # Create a commit message including the build UUID. This allows us
            # to collect all commits of a build across repositories and thereby
            # see the changes made to the entire system between any two builds.
            message = 'Morph build %s\n\nSystem branch: %s\n' % \
                      (build_uuid, system_branch)

            # Write and commit the tree and update the temporary build ref.
            tree = self.app.runcmd(
                    ['git', 'write-tree'], cwd=repo_dir, env=env).strip()
            commit = self.app.runcmd(
                    ['git', 'commit-tree', tree, '-p', parent_sha1],
                     feed_stdin=message, cwd=repo_dir, env=env).strip()
            self.app.runcmd(
                    ['git', 'update-ref', '-m', message,
                     'refs/heads/%s' % build_ref, commit],
                    cwd=repo_dir, env=env)

    def push_build_refs(self, build_repos):
        for repo, info in build_repos.iteritems():
            self.app.status(msg='%(repo)s: Pushing build branch', repo=repo)
            self.app.runcmd(['git', 'push', 'origin', '%s:%s' %
                             (info['build-ref'], info['build-ref'])],
                            cwd=info['dirname'])

    def delete_remote_build_refs(self, build_repos):
        for repo, info in build_repos.iteritems():
            self.app.status(msg='%(repo)s: Deleting remote build branch',
                            repo=repo)
            self.app.runcmd(['git', 'push', 'origin',
                             ':%s' % info['build-ref']], cwd=info['dirname'])

    def foreach(self, args):
        '''Run a command in each repository checked out in a system branch

        For simplicity, this simply iterates repositories in the directory
        rather than walking through the morphologies as 'morph merge' does.

        Morph will interpret switch arguments, so you should separate the
        command with --, as in the following example:

            morph foreach -- git status --short

        '''

        if len(args) == 0:
            raise cliapp.AppException('morph foreach expects a command to run')

        workspace = self.deduce_workspace()
        branch, branch_path = self.deduce_system_branch()
        root_repo_dir = self.get_branch_config(branch_path, 'branch.root')

        dirs = [d for d in self.walk_special_directories(
                    branch_path, special_subdir='.git')
                if os.path.basename(d) != root_repo_dir]
        dirs.sort()
        root_repo_path = os.path.join(branch_path, root_repo_dir)
        for d in [root_repo_path] + dirs:
            try:
                repo = self.get_repo_config(d, 'morph.repository')
            except cliapp.AppException:
                continue

            if d != root_repo_path:
                self.app.output.write('\n')
            self.app.output.write('%s\n' % repo)

            status, output, error = self.app.runcmd_unchecked(args, cwd=d)
            self.app.output.write(output)
            if status != 0:
                self.app.output.write(error)
                raise cliapp.AppException(
                    'Command failed at repo %s: %s' % (repo, ' '.join(args)))
