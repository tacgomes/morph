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
import copy
import glob
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
        # User-facing commands
        self.app.add_subcommand('init', self.init, arg_synopsis='[DIR]')
        self.app.add_subcommand('branch', self.branch,
                                arg_synopsis='REPO NEW [OLD]')
        self.app.add_subcommand('checkout', self.checkout,
                                arg_synopsis='REPO BRANCH')
        self.app.add_subcommand('merge', self.merge,
                                arg_synopsis='BRANCH')
        self.app.add_subcommand('edit', self.edit,
                                arg_synopsis='SYSTEM STRATUM [CHUNK]')
        self.app.add_subcommand('petrify', self.petrify)
        self.app.add_subcommand('unpetrify', self.unpetrify)
        self.app.add_subcommand('tag', self.tag)
        self.app.add_subcommand('build', self.build,
                                arg_synopsis='SYSTEM')
        self.app.add_subcommand('status', self.status)
        self.app.add_subcommand('branch-from-image', self.branch_from_image,
                                 arg_synopsis='REPO BRANCH [METADATADIR]')

        # Advanced commands
        self.app.add_subcommand('foreach', self.foreach,
                                arg_synopsis='-- COMMAND')

        # Plumbing commands (FIXME: should be hidden from --help by default)
        self.app.add_subcommand('workspace', self.workspace,
                                arg_synopsis='')
        self.app.add_subcommand('show-system-branch', self.show_system_branch,
                                arg_synopsis='')
        self.app.add_subcommand('show-branch-root', self.show_branch_root,
                                arg_synopsis='')

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
            try:
                original_repo = self.get_repo_config(
                    dirname, 'morph.repository')
            except cliapp.AppException:
                # The user may have manually put a git repo in the branch
                continue
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

    def get_head(self, repo_path):
        '''Return the ref that the working tree is on for a repo'''

        ref = self.app.runcmd(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                              cwd=repo_path).strip()
        if ref == 'HEAD':
            ref = 'detached HEAD'
        return ref

    def get_uncommitted_changes(self, repo_dir, env={}):
        status = self.app.runcmd(['git', 'status', '--porcelain'],
                                 cwd=repo_dir, env=env)
        changes = []
        for change in status.strip().splitlines():
            xy, paths = change.strip().split(' ', 1)
            if xy != '??':
                changes.append(paths.split()[0])
        return changes

    def get_unmerged_changes(self, repo_dir, env={}):
        '''Identifies files which have unresolved merge conflicts'''

        # The second column of the git command output is set either if the
        # file has changes in the working tree or if it has conflicts.
        status = self.app.runcmd(['git', 'status', '--porcelain'],
                                 cwd=repo_dir, env=env)
        changes = []
        for change in status.strip().splitlines():
            xy, paths = change[0:2], change[2:].strip()
            if xy[1] != ' ' and xy != '??':
                changes.append(paths.split()[0])
        return changes

    def resolve_ref(self, repodir, ref):
        try:
            return self.app.runcmd(['git', 'rev-parse', '--verify', ref],
                                   cwd=repodir)[0:40]
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
        target_path = os.path.abspath(dirname)
        repo.clone_checkout(ref, target_path)

        # Remember the repo name we cloned from in order to be able
        # to identify the repo again later using the same name, even
        # if the user happens to rename the directory.
        self.set_repo_config(dirname, 'morph.repository', reponame)

        # Create a UUID for the clone. We will use this for naming
        # temporary refs, e.g. for building.
        self.set_repo_config(dirname, 'morph.uuid', uuid.uuid4().hex)

        # URL configuration
        morphlib.git.set_remote(self.app.runcmd, dirname, 'origin', repo.url)
        self.set_repo_config(
            dirname, 'url.%s.pushInsteadOf' % resolver.push_url(reponame),
            resolver.pull_url(reponame))
        morphlib.git.update_submodules(self.app, target_path)

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
            filename = '%s.morph at ref %s in %s' % (name, ref, repo_dir)
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

        try:
            morphology = morphlib.morph2.Morphology(text)
        except ValueError as e:
            raise morphlib.Error("Error parsing %s: %s" %
                                 (filename, str(e)))

        self._validate_morphology(morphology, '%s.morph' % name)

        return morphology

    def _validate_morphology(self, morphology, basename):
        # FIXME: This really should be in MorphologyFactory. Later.
        
        def require(field):
            if field not in morphology:
                raise morphlib.Error(
                    'Required field "%s" is missing from morphology %s' %
                        (field, basename))
        
        required = {
            'system': [
                'name',
                'system-kind',
                'arch',
                'strata',
            ],
            'stratum': [
                'name',
                'chunks',
            ],
            'chunk': [
                'name',
            ]
        }
        
        also_known = {
            'system': [
                'kind',
                'description',
                'disk-size',
                '_disk-size',
                'configuration-extensions',
            ],
            'stratum': [
                'kind',
                'description',
                'build-depends',
            ],
            'chunk': [
                'kind',
                'description',
                'build-system',
                'configure-commands',
                'build-commands',
                'test-commands',
                'install-commands',
                'max-jobs',
                'chunks',
            ]
        }
        
        require('kind')
        kind = morphology['kind']
        if kind not in required:
            raise morphlib.Error(
                'Unknown morphology kind "%s" in %s' % (kind, basename))
        for field in required[kind]:
            require(field)
            
        known = required[kind] + also_known[kind]
        for field in morphology.keys():
            if field not in known:
                msg = 'Unknown field "%s" in %s' % (field, basename)
                logging.warning(msg)
                self.app.status(msg=msg)

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
    def iterate_branch_repos(branch_path, root_repo_path):
        '''Produces a sorted list of component repos in a branch checkout'''

        dirs = [d for d in BranchAndMergePlugin.walk_special_directories(
                    branch_path, special_subdir='.git')
                if not os.path.samefile(d, root_repo_path)]
        dirs.sort()

        for d in [root_repo_path] + dirs:
            yield d

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

    def read_metadata(self, metadata_path):
        '''Load every metadata file in `metadata_path`.
        
           Given a directory containing metadata, load them into memory
           and retain the id of the system.

           Returns the cache_key of the system and a mapping of cache_key
           to metadata.
        '''
        self.app.status(msg='Reading metadata', chatty=True)
        metadata_cache_id_lookup = {}
        system_key = None
        for path in sorted(glob.iglob(os.path.join(metadata_path, '*.meta'))):
            with open(path) as f:
                metadata = morphlib.util.json.load(f)
                cache_key = metadata['cache-key']
                metadata_cache_id_lookup[cache_key] = metadata

                if metadata['kind'] == 'system':
                    if system_key is not None:
                        raise morphlib.Error(
                            "Metadata directory contains multiple systems.")
                    system_key = cache_key

        if system_key is None:
            raise morphlib.Error(
               "Metadata directory does not contain any systems.")

        return system_key, metadata_cache_id_lookup

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

    def _create_branch(self, workspace, branch_name, repo, original_ref):
        '''Create a branch called branch_name based off original_ref.
           
           NOTE: self.lrc and self.rrc need to be initialized before
                 calling since clone_to_directory uses them indirectly via
                 get_cached_repo
        '''
        branch_dir = os.path.join(workspace, branch_name)
        os.makedirs(branch_dir)
        try:
            # Create a .morph-system-branch directory to clearly identify
            # this directory as a morph system branch.
            os.mkdir(os.path.join(branch_dir, '.morph-system-branch'))

            # Remember the system branch name and the repository we branched
            # off from initially.
            self.set_branch_config(branch_dir, 'branch.name', branch_name)
            self.set_branch_config(branch_dir, 'branch.root', repo)

            # Generate a UUID for the branch. We will use this for naming
            # temporary refs, e.g. building.
            self.set_branch_config(branch_dir, 'branch.uuid', uuid.uuid4().hex)

            # Clone into system branch directory.
            repo_dir = os.path.join(branch_dir, self.convert_uri_to_path(repo))
            self.clone_to_directory(repo_dir, repo, original_ref)

            # Create a new branch in the local morphs repository.
            if original_ref != branch_name:
                self.app.runcmd(['git', 'checkout', '-b', branch_name,
                                 original_ref], cwd=repo_dir)

            return branch_dir
        except:
            self.remove_branch_dir_safe(workspace, branch_name)
            raise

    def branch(self, args):
        '''Create a new system branch.'''

        if len(args) not in [2, 3]:
            raise cliapp.AppException('morph branch needs name of branch '
                                      'as parameter')

        repo = args[0]
        new_branch = args[1]
        commit = 'master' if len(args) == 2 else args[2]

        self.lrc, self.rrc = morphlib.util.new_repo_caches(self.app)
        if self.lrc.get_repo(repo).ref_exists(new_branch):
            raise cliapp.AppException('branch %s already exists in '
                                      'repository %s' % (new_branch, repo))

        # Create the system branch directory.
        workspace = self.deduce_workspace()
        self._create_branch(workspace, new_branch, repo, commit)

    def checkout(self, args):
        '''Check out an existing system branch.'''

        if len(args) != 2:
            raise cliapp.AppException('morph checkout needs a repo and the '
                                      'name of a branch as parameters')

        repo = args[0]
        system_branch = args[1]

        self.lrc, self.rrc = morphlib.util.new_repo_caches(self.app)

        # Create the system branch directory.
        workspace = self.deduce_workspace()
        self._create_branch(workspace, system_branch, repo, system_branch)

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

    def make_available(self, spec, branch, branch_dir, root_repo,
                       root_repo_dir):
        '''Check out the morphology that 'spec' refers to, for editing'''

        if spec['repo'] == root_repo:
            # This is only possible for stratum morphologies
            repo_dir = root_repo_dir
            if spec['ref'] != branch:
                # Bring the morphology forward from its ref to the current HEAD
                repo = self.lrc.get_repo(root_repo)
                m = repo.load_morphology(spec['ref'], spec['morph'])
                self.save_morphology(root_repo_dir, spec['morph'], m)
                self.log_change(spec['repo'],
                    '"%s" copied from "%s" to "%s"' %
                    (spec['morph'], spec['ref'], branch))
        else:
            repo_dir = self.checkout_repository(
                branch_dir, spec['repo'], branch, parent_ref=spec['ref'])
        return repo_dir

    def edit(self, args):
        '''Edit a component in a system branch.'''

        if len(args) not in (2, 3):
            raise cliapp.AppException(
                'morph edit must either get a system and a stratum '
                'or a system, a stratum and a chunk as arguments')

        workspace = self.deduce_workspace()
        branch, branch_dir = self.deduce_system_branch()

        # Find out which repository we branched off from.
        root_repo = self.get_branch_config(branch_dir, 'branch.root')
        root_repo_dir = self.find_repository(branch_dir, root_repo)

        system_name = args[0]
        stratum_name = args[1]
        chunk_name = args[2] if len(args) > 2 else None

        self.lrc, self.rrc = morphlib.util.new_repo_caches(self.app)

        # We need to touch every stratum in the system, not just the target
        # the user specified, because others may have build-depends that
        # point to the edited stratum.
        system_morphology = self.load_morphology(root_repo_dir, system_name)

        # Test that the specified stratum exists in the system
        self.get_edit_info(system_name, system_morphology, stratum_name)

        for stratum_spec in system_morphology['strata']:
            stratum_repo_dir = self.make_available(
                stratum_spec, branch, branch_dir, root_repo, root_repo_dir)
            stratum_morphology = self.load_morphology(
                stratum_repo_dir, stratum_spec['morph'])
            changed = False

            if stratum_spec['morph'] == stratum_name:
                if chunk_name is not None:
                    # Change the stratum's ref to the chunk
                    chunk_spec = self.get_edit_info(
                        stratum_name, stratum_morphology, chunk_name,
                        collection='chunks')

                    if 'unpetrify-ref' in chunk_spec:
                        chunk_spec['ref'] = chunk_spec['unpetrify-ref']
                        del chunk_spec['unpetrify-ref']

                    self.make_available(
                        chunk_spec, branch, branch_dir, root_repo,
                        root_repo_dir)

                    if chunk_spec['ref'] != branch:
                        chunk_spec['ref'] = branch

                    self.log_change(stratum_spec['repo'],
                        '"%s" now includes "%s" from "%s"' %
                        (stratum_name, chunk_name, branch))
                changed = True
            else:
                # Update build-depends in other strata that point to this one
                if stratum_morphology['build-depends'] is not None:
                    for bd_spec in stratum_morphology['build-depends']:
                        if bd_spec['morph'] == stratum_name:
                            bd_spec['ref'] = branch
                            changed = True
                            break

            if changed:
                stratum_spec['ref'] = branch
                self.save_morphology(stratum_repo_dir, stratum_spec['morph'],
                                     stratum_morphology)
                self.log_change(root_repo,
                    '"%s" now includes "%s" from "%s"' %
                    (system_name, stratum_name, branch))

        self.save_morphology(root_repo_dir, system_name, system_morphology)

        self.print_changelog('The following changes were made but have not '
                             'been committed')

    def _get_repo_name(self, alias_resolver, metadata):
        '''Attempt to find the best name for the repository.

           A defined repo-alias is preferred, but older builds may
           not have it.

           A guessed repo-alias is the next best thing, but there may
           be none or more alilases that would resolve to that URL, so
           if there are any, use the shortest as it is likely to be
           the most specific.

           If all else fails just use the URL.
        '''
        if 'repo-alias' in metadata:
            return metadata['repo-alias']

        repo_url = metadata['repo']
        aliases = alias_resolver.aliases_from_url(repo_url)

        if len(aliases) >= 1:
            # If there are multiple valid aliases, use the shortest
            return min(aliases, key=len)

        # If there are no aliases, just return the url
        return repo_url
            
    def _resolve_refs_from_metadata(self, alias_resolver,
                                    metadata_cache_id_lookup):
        '''Pre-resolve a set of refs from metadata.
        
           Resolved refs are a dict as {(repo, ref): sha1}.

           If the metadata contains the repo-alias then every
           metadata item adds the mapping of its repo-alias and ref
           to the commit it was built with.

           If the repo-alias does not exist, such as if the image was
           built before that field was added, then mappings of every
           possible repo url are added.
        '''
        resolved_refs = {}
        for md in metadata_cache_id_lookup.itervalues():
            if 'repo-alias' in md:
                repourls = [md['repo-alias']]
            else:
                repourls = [md['repo']] 
                repourls.extend(alias_resolver.aliases_from_url(md['repo']))
            for repourl in repourls:
                resolved_refs[repourl, md['original_ref']] = md['sha1']
        return resolved_refs

    def branch_from_image(self, args):
        '''Given the contents of a /baserock directory, produce a branch
           of the System, petrified to when the System was made.
        '''
        if len(args) not in (2, 3):
            raise cliapp.AppException(
                'branch-from-image needs repository, ref and path to metadata')
        root_repo = args[0]
        branch = args[1]
        metadata_path = '/baserock' if len(args) == 2 else args[2]
        workspace = self.deduce_workspace()
        self.lrc, self.rrc = morphlib.util.new_repo_caches(self.app)

        alias_resolver = morphlib.repoaliasresolver.RepoAliasResolver(
            self.app.settings['repo-alias'])

        system_key, metadata_cache_id_lookup = self.read_metadata(
            metadata_path)
        
        system_metadata = metadata_cache_id_lookup[system_key]
        repo = self._get_repo_name(alias_resolver, system_metadata)

        # Which repo to use? Specified or deduced?
        branch_dir = self._create_branch(workspace, branch, repo,
                                         system_metadata['sha1'])

        # Resolve refs from metadata so petrify substitutes these refs
        # into morphologies instead of the current state of the branches
        resolved_refs = self._resolve_refs_from_metadata(
            alias_resolver,
            metadata_cache_id_lookup)

        branch_root_dir = self.find_repository(branch_dir, repo)
        name = system_metadata['morphology'][:-len('.morph')]
        morphology = self.load_morphology(branch_root_dir, name)
        self.petrify_morphology(branch, branch_dir,
                                repo, branch_root_dir,
                                repo, branch_root_dir, # not a typo
                                branch, name, morphology,
                                petrified_morphologies=set(),
                                resolved_refs=resolved_refs,
                                update_working_tree=True)

    def petrify(self, args):
        '''Convert all chunk refs in a system branch to be fixed SHA1s

        This isolates the branch from changes made by other developers in the
        chunk repositories.
        '''

        # Stratum refs are not petrified, because they must all be edited to
        # set the new chunk refs, which requires branching them all for the
        # current branch - so they will not be updated outside of the user's
        # control in any case. Chunks that have already been edited on the
        # current branch are also not petrified.

        if len(args) != 0:
            raise cliapp.AppException('morph petrify takes no arguments')

        workspace = self.deduce_workspace()
        branch, branch_path = self.deduce_system_branch()
        root_repo = self.get_branch_config(branch_path, 'branch.root')
        root_repo_dir = self.find_repository(branch_path, root_repo)
        self.lrc, self.rrc = morphlib.util.new_repo_caches(self.app)

        # We must first get the full set of strata. One same stratum may be
        # in multiple systems and each system may use a different ref.
        strata = {}
        for f in sorted(glob.iglob(os.path.join(root_repo_dir, '*.morph'))):
            name = os.path.basename(f)[:-len('.morph')]
            morphology = self.load_morphology(root_repo_dir, name)
            if morphology['kind'] != 'system':
                continue

            for stratum_info in morphology['strata']:
                key = (stratum_info['repo'], stratum_info['morph'])
                if key in strata:
                    original_ref = strata[key]
                    if stratum_info['ref'] == branch:
                        strata[key] = branch
                    elif stratum_info['ref'] != original_ref:
                        if original_ref != branch:
                            self.app.output.write(
                                'WARNING: not merging any differences from '
                                'ref %s into %s of stratum %s\n' %
                                (stratum_info['ref'], original_ref,
                                 stratum_info['morph']))
                        stratum_info['ref'] = branch
                else:
                    strata[key] = stratum_info['ref']
                    stratum_info['ref'] = branch
            self.save_morphology(root_repo_dir, name, morphology)

        for (repo, morph), ref in strata.iteritems():
            repo_dir = self.make_available(
                { 'repo': repo, 'ref': ref, 'morph': morph},
                branch, branch_path, root_repo, root_repo_dir)

            stratum = self.load_morphology(repo_dir, morph)

            for chunk_info in stratum['chunks']:
                if (chunk_info['ref'] != branch and
                        'unpetrify-ref' not in chunk_info):
                    commit_sha1, tree_sha1 = self.app.resolve_ref(
                        self.lrc, self.rrc, chunk_info['repo'],
                        chunk_info['ref'],
                        update=not self.app.settings['no-git-update'])
                    chunk_info['unpetrify-ref'] = chunk_info['ref']
                    chunk_info['ref'] = commit_sha1
            self.save_morphology(repo_dir, morph, stratum)

        self.print_changelog('The following changes were made but have not '
                             'been committed')

    def unpetrify(self, args):
        '''Reverse the process of petrification'''

        # This function makes no attempt to 'unedit' strata that were branched
        # solely so they could be petrified.

        if len(args) != 0:
            raise cliapp.AppException('morph unpetrify takes no arguments')

        self.lrc, self.rrc = morphlib.util.new_repo_caches(self.app)

        workspace = self.deduce_workspace()
        branch, branch_path = self.deduce_system_branch()
        root_repo = self.get_branch_config(branch_path, 'branch.root')
        root_repo_dir = self.find_repository(branch_path, root_repo)

        for f in sorted(glob.iglob(os.path.join(root_repo_dir, '*.morph'))):
            name = os.path.basename(f)[:-len('.morph')]
            morphology = self.load_morphology(root_repo_dir, name)
            if morphology['kind'] != 'system':
                continue

            for stratum_info in morphology['strata']:
                repo_dir = self.make_available(
                    stratum_info, branch, branch_path, root_repo,
                    root_repo_dir)
                stratum_info['ref'] = branch

                stratum = self.load_morphology(repo_dir, stratum_info['morph'])

                for chunk_info in stratum['chunks']:
                    if 'unpetrify-ref' in chunk_info:
                        chunk_info['ref'] = chunk_info['unpetrify-ref']
                        del chunk_info['unpetrify-ref']
                self.save_morphology(repo_dir, stratum_info['morph'], stratum)

            self.save_morphology(root_repo_dir, name, morphology)

        self.print_changelog('The following changes were made but have not '
                             'been committed')

    def tag(self, args):
        if len(args) < 1:
            raise cliapp.AppException('morph tag expects a tag name')

        tagname = args[0]

        # Deduce workspace, system branch and branch root repository.
        workspace = self.deduce_workspace()
        branch, branch_dir = self.deduce_system_branch()
        branch_root = self.get_branch_config(branch_dir, 'branch.root')
        branch_root_dir = self.find_repository(branch_dir, branch_root)

        # Prepare an environment for our internal index file.
        # This index file allows us to commit changes to a tree without
        # git noticing any change in the working tree or its own index.
        env = dict(os.environ)
        env['GIT_INDEX_FILE'] = os.path.join(
                branch_root_dir, '.git', 'morph-tag-index')

        # Extract git arguments that deal with the commit message.
        # This is so that we can use them for creating the tag commit.
        msg = None
        msg_args = []
        for i in xrange(0, len(args)):
            if args[i] == '-m' or args[i] == '-F':
                if i < len(args)-1:
                    msg_args.append(args[i])
                    msg_args.append(args[i+1])
                    if args[i] == '-m':
                        msg = args[i+1]
                    else:
                        msg = open(args[i+1]).read()
            elif args[i].startswith('--message='):
                msg_args.append(args[i])
                msg = args[i][len('--message='):]

        # Fail if no commit message was provided.
        if not msg or not msg_args:
            raise cliapp.AppException(
                    'Commit message expected. Please run one of '
                    'the following commands to provide one:\n'
                    '  morph tag NAME -- -m "Message"\n'
                    '  morph tag NAME -- --message="Message"\n'
                    '  morph tag NAME -- -F <message file>')

        # Abort if the tag already exists.
        # FIXME At the moment this only checks the local repo in the
        # workspace, not the remote repo cache or the local repo cache.
        if self.ref_exists_locally(branch_root_dir, 'refs/tags/%s' % tagname):
            raise cliapp.AppException('%s: Tag "%s" already exists' %
                                      (branch_root, tagname))

        self.app.status(msg='%(repo)s: Preparing tag commit',
                        repo=branch_root)

        # Read current tree into the internal index.
        parent_sha1 = self.resolve_ref(branch_root_dir, branch)
        self.app.runcmd(['git', 'read-tree', parent_sha1],
                        cwd=branch_root_dir, env=env)

        self.app.status(msg='%(repo)s: Petrifying everything',
                        repo=branch_root)

        # Petrify everything.
        self.lrc, self.rrc = morphlib.util.new_repo_caches(self.app)
        self.petrify_everything(branch, branch_dir,
                                branch_root, branch_root_dir,
                                tagname, env)

        self.app.status(msg='%(repo)s: Creating tag commit',
                       repo=branch_root)

        # Create a dangling commit.
        commit = self.create_tag_commit(
                branch_root_dir, tagname, msg, env)

        self.app.status(msg='%(repo)s: Creating annotated tag "%(tag)s"',
                        repo=branch_root, tag=tagname)

        # Create an annotated tag for this commit.
        self.create_annotated_tag(branch_root_dir, commit, env, args)

    def ref_exists_locally(self, repo_dir, ref):
        try:
            morphlib.git.rev_parse(self.app.runcmd, repo_dir, ref)
            return True
        except cliapp.AppException:
            return False

    def petrify_everything(self, branch, branch_dir,
            branch_root, branch_root_dir, tagref, env=os.environ,
            resolved_refs=None, update_working_tree=False):
        petrified_morphologies = set()
        resolved_refs = resolved_refs or {}
        for f in sorted(glob.iglob(os.path.join(branch_root_dir, '*.morph'))):
            name = os.path.basename(f)[:-len('.morph')]
            morphology = self.load_morphology(branch_root_dir, name)
            self.petrify_morphology(branch, branch_dir,
                                    branch_root, branch_root_dir,
                                    branch_root, branch_root_dir,
                                    tagref, name, morphology,
                                    petrified_morphologies, resolved_refs,
                                    env, update_working_tree)

    def petrify_morphology(self, branch, branch_dir,
                           branch_root, branch_root_dir, repo, repo_dir,
                           tagref, name, morphology,
                           petrified_morphologies, resolved_refs,
                           env=os.environ, update_working_tree=False):
        self.app.status(msg='%(repo)s: Petrifying morphology \"%(morph)s\"',
                        repo=repo, morph=name)

        # Mark morphology as petrified so we don't petrify it twice.
        petrified_morphologies.add(morphology)

        # Resolve the refs of all build dependencies (strata) and strata
        # in the morphology into commit SHA1s.
        strata = []
        if 'build-depends' in morphology and morphology['build-depends']:
            strata += morphology['build-depends']
        if 'strata' in morphology and morphology['strata']:
            strata += morphology['strata']
        for info in strata:
            # Obtain the commit SHA1 this stratum would be built from.
            commit = self.resolve_info(info, resolved_refs)
            stratum_repo_dir = self.make_available(
                    info, branch, branch_dir, repo, repo_dir)
            info['ref'] = branch

            # Load the stratum morphology and petrify it recursively if
            # that hasn't happened yet.
            stratum = self.load_morphology(stratum_repo_dir, info['morph'])
            if not stratum in petrified_morphologies:
                self.petrify_morphology(branch, branch_dir,
                                        branch_root, branch_root_dir,
                                        info['repo'], stratum_repo_dir,
                                        tagref, info['morph'], stratum,
                                        petrified_morphologies,
                                        resolved_refs, env,
                                        update_working_tree)

            # Change the ref for this morphology to the tag we're creating.
            if info['ref'] != tagref:
                info['unpetrify-ref'] = info['ref']
                info['ref'] = tagref

            # We'll be copying all systems/strata into the tag commit
            # in the branch root repo, so make sure to note what repos
            # they all came from
            if info['repo'] != branch_root:
                info['unpetrify-repo'] = info['repo']
                info['repo'] = branch_root

        # If this morphology is a stratum, resolve the refs of all its
        # chunks into SHA1s.
        if morphology['kind'] == 'stratum':
            for info in morphology['chunks']:
                commit = self.resolve_info(info, resolved_refs)
                if info['ref'] != commit:
                    info['unpetrify-ref'] = info['ref']
                    info['ref'] = commit

        # Write the petrified morphology to a temporary file in the
        # branch root repository for inclusion in the tag commit.
        handle, tmpfile = tempfile.mkstemp(suffix='.morph')
        self.save_morphology(branch_root_dir, tmpfile, morphology)

        # Hash the petrified morphology and add it to the index
        # for the tag commit.
        sha1 = self.app.runcmd(
                ['git', 'hash-object', '-t', 'blob', '-w', tmpfile],
                cwd=branch_root_dir, env=env)
        self.app.runcmd(
                ['git', 'update-index', '--add', '--cacheinfo',
                 '100644', sha1, '%s.morph' % name],
                cwd=branch_root_dir, env=env)

        # Update the working tree if requested. This can be done with
        # git-checkout-index, but we still have the file, so use that
        if update_working_tree:
            shutil.copy(tmpfile,
                        os.path.join(branch_root_dir, '%s.morph' % name))

        # Delete the temporary file again.
        os.remove(tmpfile)

    def resolve_info(self, info, resolved_refs):
        '''Takes a morphology info and resolves its ref with cache support.'''

        key = (info['repo'], info['ref'])
        if not key in resolved_refs:
            commit_sha1, tree_sha1 = self.app.resolve_ref(
                    self.lrc, self.rrc, info['repo'], info['ref'],
                    update=not self.app.settings['no-git-update'])
            resolved_refs[key] = commit_sha1
        return resolved_refs[key]

    def create_tag_commit(self, repo_dir, tagname, msg, env):
        self.app.status(msg='%(repo)s: Creating commit for the tag',
                        repo=repo_dir)

        # Write and commit the tree.
        tree = self.app.runcmd(
                ['git', 'write-tree'], cwd=repo_dir, env=env).strip()
        commit = self.app.runcmd(
                ['git', 'commit-tree', tree, '-p', 'HEAD'],
                feed_stdin=msg, cwd=repo_dir, env=env).strip()
        return commit

    def create_annotated_tag(self, repo_dir, commit, env, args=[]):
        self.app.status(msg='%(repo)s: Creating annotated tag for '
                            'commit %(commit)s',
                        repo=repo_dir, commit=commit)

        # Create an annotated tag for the commit
        self.app.runcmd(['git', 'tag', '-a'] + args + [commit],
                        cwd=repo_dir, env=env)

    # When 'merge' is unset, git doesn't try to resolve conflicts itself in
    # those files.
    MERGE_ATTRIBUTE = '*.morph\t-merge\n'

    def disable_morph_merging(self, repo_dir):
        attributes_file = os.path.join(repo_dir, ".git", "info", "attributes")
        with open(attributes_file, 'a') as f:
            f.write(self.MERGE_ATTRIBUTE)

    def enable_morph_merging(self, repo_dir):
        attributes_file = os.path.join(repo_dir, ".git", "info", "attributes")
        with open(attributes_file, 'r') as f:
            attributes = f.read()
        if attributes == self.MERGE_ATTRIBUTE:
            os.unlink(attributes_file)
        elif attributes.endswith(self.MERGE_ATTRIBUTE):
            with morphlib.savefile.SaveFile(attributes_file, 'w') as f:
                f.write(attributes[:-len(self.MERGE_ATTRIBUTE)])

    def get_merge_files(self, repo_dir, from_sha1, to_ref, name):
        '''Returns merge base, remote and local versions of a morphology

        We already ran 'git fetch', so the remote branch is available within
        the target repository.

        '''

        base_sha1 = self.app.runcmd(['git', 'merge-base', from_sha1, to_ref],
                                    cwd=repo_dir).strip()
        base_morph = self.load_morphology(repo_dir, name, ref=base_sha1)
        from_morph = self.load_morphology(repo_dir, name, ref=from_sha1)
        to_morph = self.load_morphology(repo_dir, name, ref=to_ref)
        return base_morph, from_morph, to_morph

    def check_component(self, parent_kind, parent_path, from_info, to_info):
        assert (parent_kind in ['system', 'stratum'])

        kind = 'chunk' if parent_kind == 'stratum' else 'stratum'
        name = to_info.get('alias', to_info.get('name', to_info.get('morph')))
        path = parent_path + '.' + name

        if kind == 'chunk':
            # Only chunks can be petrified
            from_unpetrify_ref = from_info.get('unpetrify-ref', None)
            to_unpetrify_ref = to_info.get('unpetrify-ref', None)
            if from_unpetrify_ref is not None and to_unpetrify_ref is None:
                self.app.output.write(
                    'WARNING: chunk "%s" is now petrified\n' % path)
            elif from_unpetrify_ref is None and to_unpetrify_ref is not None:
                self.app.output.write(
                    'WARNING: chunk "%s" is no longer petrified\n' % path)
            elif from_unpetrify_ref != to_unpetrify_ref:
                raise cliapp.AppException(
                    'merge conflict: chunk "%s" is petrified to a different '
                    'ref in each branch' % path)

    def diff_morphologies(self, path, from_morph, to_morph):
        '''Component-level diff between two versions of a morphology'''

        def component_key(info):
            # This function needs only to be stable and reproducible
            key = info['repo'] + '|' + info['morph']
            if 'name' in info:
                key += '|' + info['name']
            return key

        if from_morph['name'] != to_morph['name']:
            # We should enforce name == filename in load_morphology()
            raise cliapp.AppException(
                'merge conflict: "name" of morphology %s (name should always '
                'match filename)' % path)
        if from_morph['kind'] != to_morph['kind']:
            raise cliapp.AppException(
                'merge conflict: "kind" of morphology %s changed from %s to %s'
                % (path, to_morph['kind'], from_morph['kind']))

        kind = to_morph['kind']

        # copy() makes a shallow copy, so editing the list elements will
        # change the actual morphologies.
        if kind == 'system':
            from_components = copy.copy(from_morph['strata'])
            to_components = copy.copy(to_morph['strata'])
        elif kind == 'stratum':
            from_components = copy.copy(from_morph['chunks'])
            to_components = copy.copy(to_morph['chunks'])
        from_components.sort(key=component_key)
        to_components.sort(key=component_key)

        # These are not set() purely because a set requires a hashable type
        intersection = [] # TO n FROM
        from_diff = []    # FROM \ TO
        to_diff = []      # TO \ FROM
        while len(from_components) > 0 and len(to_components) > 0:
            from_info = from_components.pop(0)
            to_info = to_components.pop(0)
            match = cmp(component_key(from_info), component_key(to_info))
            if match < 0:
                from_diff.append(from_info)
            elif match > 0:
                to_diff.append(to_info)
            elif match == 0:
                intersection.append((from_info, to_info))
        if len(from_components) != 0:
            from_diff.append(from_components.pop(0))
        if len(to_components) != 0:
            to_diff.append(to_components.pop(0))
        return intersection, from_diff, to_diff

    def merge_repo(self, merged_repos, from_branch_dir, from_repo, from_ref,
                   to_branch_dir, to_repo, to_ref):
        '''Merge changes for a system branch in a specific repository

        We disable merging for morphologies and do this manually later on.

        '''

        if to_repo in merged_repos:
            return merged_repos[to_repo]

        from_repo_dir = self.find_repository(from_branch_dir, from_repo)
        to_repo_dir = self.checkout_repository(to_branch_dir, to_repo, to_ref)

        if self.get_uncommitted_changes(from_repo_dir) != []:
            raise cliapp.AppException('repository %s has uncommitted '
                                      'changes' % from_repo)
        if self.get_uncommitted_changes(to_repo_dir) != []:
            raise cliapp.AppException('repository %s has uncommitted '
                                      'changes' % to_repo)

        # Fetch the local FROM branch; its sha1 will be stored in FETCH_HEAD.
        # ':' in pathnames confuses git, so we have to pass it a URL.
        from_repo_url = urlparse.urljoin('file://', from_repo_dir)
        self.app.runcmd(['git', 'fetch', from_repo_url, from_ref],
                        cwd=to_repo_dir)

        # Merge everything but the morphologies; error output is ignored (it's
        # not very good) and instead we report conflicts manually later on.
        self.disable_morph_merging(to_repo_dir)
        with open(os.path.join(to_repo_dir, '.git', 'FETCH_HEAD')) as f:
            from_sha1 = f.read(40)
        status, output, error = self.app.runcmd_unchecked(
            ['git', 'merge', '--no-commit', '--no-ff', from_sha1],
            cwd=to_repo_dir)
        self.enable_morph_merging(to_repo_dir)

        merged_repos[to_repo] = (to_repo_dir, from_sha1)
        return (to_repo_dir, from_sha1)

    def merge(self, args):
        '''Pull and merge changes from a system branch into the current one.

        The remote branch is pulled from the current workspace into the target
        repositories (so any local commits are included).

        '''

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

        def merge_chunk(parent_path, old_ci, ci):
            self.merge_repo(merged_repos,
                from_branch_dir, old_ci['repo'], from_branch,
                to_branch_dir, ci['repo'], ci['ref'])

        def merge_stratum(parent_path, old_si, si):
            path = parent_path + '.' + si['morph']

            to_repo_dir, from_sha1 = self.merge_repo(merged_repos,
                from_branch_dir, old_si['repo'], from_branch,
                to_branch_dir, si['repo'], si['ref'])
            base_morph, from_morph, to_morph = self.get_merge_files(
                to_repo_dir, from_sha1, si['ref'], si['morph'])
            intersection, from_diff, to_diff = self.diff_morphologies(
                path, from_morph, to_morph)
            for from_ci, to_ci in intersection:
                self.check_component('stratum', path, from_ci, to_ci)

            changed = False
            edited_chunks = [ci for ci in from_morph['chunks']
                             if ci['ref'] == from_branch]
            for ci in edited_chunks:
                for old_ci in to_morph['chunks']:
                    if old_ci['repo'] == ci['repo']:
                        break
                else:
                    raise cliapp.AppException(
                        'chunk %s was added within this branch and '
                        'subsequently edited. This is not yet supported: '
                        'refusing to merge.' % ci['name'])
                changed = True
                ci['ref'] = old_ci['ref']
                merge_chunk(path, old_ci, ci)
            if changed:
                self.save_morphology(to_repo_dir, si['morph'], to_morph)
                self.app.runcmd(['git', 'add', si['morph'] + '.morph'],
                                cwd=to_repo_dir)

        def merge_system(name):
            base_morph, from_morph, to_morph = self.get_merge_files(
                to_root_dir, from_sha1, to_branch, name)
            if to_morph['kind'] != 'system':
                return

            intersection, from_diff, to_diff = self.diff_morphologies(
                name, from_morph, to_morph)
            for from_si, to_si in intersection:
                self.check_component('system', name, from_si, to_si)

            changed = False
            edited_strata = [si for si in from_morph['strata']
                             if si['ref'] == from_branch]
            for si in edited_strata:
                for old_si in to_morph['strata']:
                    # We make no attempt at rename / move detection
                    if (old_si['morph'] == si['morph']
                            and old_si['repo'] == si['repo']):
                        break
                else:
                    raise cliapp.AppException(
                        'stratum %s was added within this branch and '
                        'subsequently edited. This is not yet supported: '
                        'refusing to merge.' % si['morph'])
                changed = True
                si['ref'] = old_si['ref']
                merge_stratum(name, old_si, si)
            if changed:
                self.save_morphology(to_root_dir, name, to_morph)
                self.app.runcmd(['git', 'add', f], cwd=to_root_dir)

        merged_repos = {}
        try:
            to_root_dir, from_sha1 = self.merge_repo(merged_repos,
                from_branch_dir, root_repo, from_branch,
                to_branch_dir, root_repo, to_branch)

            for f in sorted(glob.iglob(os.path.join(to_root_dir, '*.morph'))):
                name = os.path.basename(f)[:-len('.morph')]
                merge_system(name)

            success = True
            for repo_name, repo_info in merged_repos.iteritems():
                repo_dir = repo_info[0]
                conflicts = self.get_unmerged_changes(repo_dir)
                if len(conflicts) > 0:
                    self.app.output.write("Merge conflicts in %s:\n\t%s\n" %
                        (repo_name, '\n\t'.join(conflicts)))
                    success = False
                elif morphlib.git.index_has_changes(self.app.runcmd, repo_dir):
                    # Repo may not be dirty if the changes only touched refs,
                    # because they may now match the previous state.
                    msg = "Merge system branch '%s'" % from_branch
                    self.app.runcmd(['git', 'commit', '--all', '-m%s' % msg],
                                    cwd=repo_dir)
            if not success:
                raise cliapp.AppException(
                    "merge errors were encountered. Please manually merge the "
                    "target ref into %s in the remote system branch in each "
                    "case, and then repeat the 'morph merge' operation." %
                    from_branch)
            self.app.status(msg="Merge successful")
        except:
            for repo_dir, sha1 in merged_repos.itervalues():
                self.reset_work_tree_safe(repo_dir)
            raise

    def build(self, args):
        '''Build a system from the current system branch'''

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
        build_repos = self.get_system_build_repos(
                branch, branch_dir, branch_root, system_name)

        # Generate temporary build ref names for all these repositories.
        self.generate_build_ref_names(build_repos, branch_uuid)

        # Create the build refs for all these repositories and commit
        # all uncommitted changes to them, updating all references
        # to system branch refs to point to the build refs instead.
        self.update_build_refs(build_repos, branch, build_uuid, push)

        if push:
            self.push_build_refs(build_repos)
            build_branch_root = branch_root
        else:
            dirname = build_repos[branch_root]['dirname']
            build_branch_root = urlparse.urljoin('file://', dirname)

        # Run the build.
        build_command.build([build_branch_root,
                             build_repos[branch_root]['build-ref'],
                             system_name])

        if push:
            self.delete_remote_build_refs(build_repos)

        self.app.status(msg='Finished build %(uuid)s', uuid=build_uuid)

    def get_system_build_repos(self, system_branch, branch_dir,
                               branch_root, system_name):
        '''Map upstream repository URLs to their checkouts in the system branch

        Also provides the list of morphologies stored in each repository,
        grouped by kind.

        '''

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

    def inject_build_refs(self, morphology, build_repos, will_push):
        # Starting from a system or stratum morphology, update all ref
        # pointers of strata or chunks involved in a system build (represented
        # by build_repos) to point to temporary build refs of the repos
        # involved in the system build.
        def inject_build_ref(info):
            if info['repo'] in build_repos and (
                    info['morph'] in build_repos[info['repo']]['strata'] or
                    info['morph'] in build_repos[info['repo']]['chunks']):
                info['ref'] = build_repos[info['repo']]['build-ref']
                if not will_push:
                    dirname = build_repos[info['repo']]['dirname']
                    info['repo'] = urlparse.urljoin('file://', dirname)
        if morphology['kind'] == 'system':
            for info in morphology['strata']:
                inject_build_ref(info)
        elif morphology['kind'] == 'stratum':
            if morphology['build-depends'] is not None:
                for info in morphology['build-depends']:
                    inject_build_ref(info)
            for info in morphology['chunks']:
                inject_build_ref(info)

    def generate_build_ref_names(self, build_repos, branch_uuid):
        for repo, info in build_repos.iteritems():
            repo_dir = info['dirname']
            repo_uuid = self.get_repo_config(repo_dir, 'morph.uuid')
            build_ref = os.path.join(self.app.settings['build-ref-prefix'],
                                     branch_uuid, repo_uuid)
            info['build-ref'] = build_ref

    def update_build_refs(self, build_repos, system_branch, build_uuid,
                          will_push):
        '''Update build branches for each repository with any local changes '''

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
            system_branch_sha1 = self.resolve_ref(repo_dir, system_branch)
            parent_sha1 = self.resolve_ref(repo_dir, build_ref)
            if not parent_sha1:
                parent_sha1 = system_branch_sha1

            # Prepare an environment with our internal index file.
            # This index file allows us to commit changes to a tree without
            # git noticing any change in working tree or its own index.
            env = dict(os.environ)
            env['GIT_INDEX_FILE'] = os.path.join(
                    repo_dir, '.git', 'morph-index')
            env['GIT_COMMITTER_NAME'] = committer_name
            env['GIT_COMMITTER_EMAIL'] = committer_email

            # Read tree from current HEAD into the morph index.
            self.app.runcmd(['git', 'read-tree', system_branch_sha1],
                            cwd=repo_dir, env=env)

            self.app.status(msg='%(repo)s: Adding uncommitted changes to '
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
                self.inject_build_refs(morphology, build_repos, will_push)
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

    def status(self, args):
        '''Show information about the current system branch or workspace'''
        if len(args) != 0:
            raise cliapp.AppException('morph status takes no arguments')

        workspace = self.deduce_workspace()
        try:
            branch, branch_path = self.deduce_system_branch()
        except cliapp.AppException:
            branch = None

        if branch is None:
            self.app.output.write("System branches in current workspace:\n")
            branch_dirs = sorted(self.walk_special_directories(
                workspace, special_subdir='.morph-system-branch'))
            for dirname in branch_dirs:
                branch = self.get_branch_config(dirname, 'branch.name')
                self.app.output.write("    %s\n" % branch)
            return

        root_repo = self.get_branch_config(branch_path, 'branch.root')
        root_repo_path = self.find_repository(branch_path, root_repo)

        self.app.output.write("On branch %s, root %s\n" % (branch, root_repo))

        has_uncommitted_changes = False
        for d in self.iterate_branch_repos(branch_path, root_repo_path):
            try:
                repo = self.get_repo_config(d, 'morph.repository')
            except cliapp.AppException:
                self.app.output.write(
                    '    %s: not part of system branch\n' % d)
                continue
            head = self.get_head(d)
            if head != branch:
                self.app.output.write(
                    '    %s: unexpected ref checked out "%s"\n' % (repo, head))
            if len(self.get_uncommitted_changes(d)) > 0:
                has_uncommitted_changes = True
                self.app.output.write('    %s: uncommitted changes\n' % repo)

        if not has_uncommitted_changes:
            self.app.output.write("\nNo repos have outstanding changes.\n")

    def foreach(self, args):
        '''Run a command in each repository checked out in a system branch

        Use -- before specifying the command to separate its arguments from
        Morph's own arguments.

        '''

        # For simplicity, this simply iterates repositories in the directory
        # rather than walking through the morphologies as 'morph merge' does.

        if len(args) == 0:
            raise cliapp.AppException('morph foreach expects a command to run')

        workspace = self.deduce_workspace()
        branch, branch_path = self.deduce_system_branch()

        root_repo = self.get_branch_config(branch_path, 'branch.root')
        root_repo_path = self.find_repository(branch_path, root_repo)

        for d in self.iterate_branch_repos(branch_path, root_repo_path):
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

    def workspace(self, args):
        '''Find the toplevel directory of the current workspace'''

        self.app.output.write('%s\n' % self.deduce_workspace())

    def show_system_branch(self, args):
        '''Print name of current system branch'''

        branch, dirname = self.deduce_system_branch()
        self.app.output.write('%s\n' % branch)

    def show_branch_root(self, args):
        '''Print name of the repository holding the system morphologies'''

        workspace = self.deduce_workspace()
        system_branch, branch_dir = self.deduce_system_branch()
        branch_root = self.get_branch_config(branch_dir, 'branch.root')
        self.app.output.write('%s\n' % branch_root)
