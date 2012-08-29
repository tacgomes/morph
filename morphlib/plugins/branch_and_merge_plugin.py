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
import os
import json
import glob
import tempfile

import morphlib


class BranchAndMergePlugin(cliapp.Plugin):

    system_repo_base = 'morphs'
    system_repo_name = 'baserock:%s' % system_repo_base

    def enable(self):
        self.app.add_subcommand('petrify', self.petrify,
                                arg_synopsis='STRATUM...')
        self.app.add_subcommand('init', self.init, arg_synopsis='[DIR]')
        self.app.add_subcommand('workspace', self.workspace,
                                arg_synopsis='')
        self.app.add_subcommand('branch', self.branch,
                                arg_synopsis='NEW [OLD]')
        self.app.add_subcommand('checkout', self.checkout,
                                arg_synopsis='BRANCH')
        self.app.add_subcommand('show-system-branch', self.show_system_branch,
                                arg_synopsis='')
        self.app.add_subcommand('merge', self.merge,
                                arg_synopsis='BRANCH REPO...')
        self.app.add_subcommand('edit', self.edit,
                                arg_synopsis='REPO [REF]')

    def disable(self):
        pass

    @staticmethod
    def deduce_workspace():
        dirname = os.getcwd()
        while dirname != '/':
            dot_morph = os.path.join(dirname, '.morph')
            if os.path.isdir(dot_morph):
                return dirname
            dirname = os.path.dirname(dirname)
        raise cliapp.AppException("Can't find the workspace directory")

    @staticmethod
    def is_system_branch_directory(dirname):
        return os.path.isdir(os.path.join(dirname, '.morph-system-branch'))

    @classmethod
    def deduce_system_branch(cls):
        # 1. Deduce the workspace. If this fails, we're not inside a workspace.
        workspace = cls.deduce_workspace()

        # 2. We're in a workspace. Check if we're inside a system branch.
        #    If we are, return its name.
        dirname = os.getcwd()
        while dirname != workspace and dirname != '/':
            if cls.is_system_branch_directory(dirname):
                return os.path.relpath(dirname, workspace)
            dirname = os.path.dirname(dirname)

        # 3. We're in a workspace but not inside a branch. Try to find a
        #    branch directory in the directories below the current working
        #    directory. Avoid ambiguousity by only recursing deeper if there
        #    is only one subdirectory.
        visited = set()
        for dirname, subdirs, files in os.walk(os.getcwd(), followlinks=True):
            # Avoid infinite recursion.
            if dirname in visited:
                break
            visited.add(dirname)

            if cls.is_system_branch_directory(dirname):
                return os.path.relpath(dirname, workspace)

            # Do not recurse deeper if we have more than one
            # non-hidden directory.
            if len([x for x in subdirs if not x.startswith('.')]) > 1:
                break

        raise cliapp.AppException("Can't find the system branch directory")

    @staticmethod
    def clone_to_directory(app, dirname, reponame, ref):
        '''Clone a repository below a directory.

        As a side effect, clone it into the local repo cache.

        '''

        # Setup.
        cache = morphlib.util.new_repo_caches(app)[0]
        resolver = morphlib.repoaliasresolver.RepoAliasResolver(
            app.settings['repo-alias'])

        # Get the repository into the cache; make sure it is up to date.
        repo = cache.cache_repo(reponame)
        if not app.settings['no-git-update']:
            repo.update()

        # Clone it from cache to target directory.
        repo.checkout(ref, os.path.abspath(dirname))

        # Set the origin to point at the original repository.
        morphlib.git.set_remote(app.runcmd, dirname, 'origin', repo.url)

        # Add push url rewrite rule to .git/config.
        app.runcmd(['git', 'config',
                    ('url.%s.pushInsteadOf' %
                     resolver.push_url(reponame)),
                    resolver.pull_url(reponame)], cwd=dirname)

        app.runcmd(['git', 'remote', 'update'], cwd=dirname)

    @staticmethod
    def resolve_reponame(app, reponame):
        '''Return the full pull URL of a reponame.'''

        resolver = morphlib.repoaliasresolver.RepoAliasResolver(
            app.settings['repo-alias'])
        return resolver.pull_url(reponame)

    @staticmethod
    def load_morphologies(dirname):
        pattern = os.path.join(dirname, '*.morph')
        for filename in glob.iglob(pattern):
            with open(filename) as f:
                text = f.read()
            morphology = morphlib.morph2.Morphology(text)
            yield filename, morphology

    @classmethod
    def morphs_for_repo(cls, app, morphs_dirname, repo):
        for filename, morph in cls.load_morphologies(morphs_dirname):
            if morph['kind'] == 'stratum':
                for spec in morph['sources']:
                    spec_repo = cls.resolve_reponame(app, spec['repo'])
                    if spec_repo == repo:
                        yield filename, morph
                        break

    @classmethod
    def find_edit_ref(cls, app, morphs_dirname, repo):
        for filename, morph in cls.morphs_for_repo(app, morphs_dirname, repo):
            for spec in morph['sources']:
                spec_repo = cls.resolve_reponame(app, spec['repo'])
                if spec_repo == repo:
                    return spec['ref']
        return None

    @staticmethod
    def write_morphology(filename, morphology):
        as_dict = {}
        for key in morphology.keys():
            value = morphology[key]
            if value:
                as_dict[key] = value
        with morphlib.savefile.SaveFile(filename, 'w') as f:
            json.dump(as_dict, fp=f, indent=4, sort_keys=True)
            f.write('\n')

    def petrify(self, args):
        '''Make refs to chunks be absolute SHA-1s.'''

        app = self.app
        cache = morphlib.util.new_repo_caches(app)[0]

        for filename in args:
            with open(filename) as f:
                morph = morphlib.morph2.Morphology(f.read())

            if morph['kind'] != 'stratum':
                app.status(msg='Not a stratum: %(filename)s',
                           filename=filename)
                continue

            app.status(msg='Petrifying %(filename)s', filename=filename)

            for source in morph['sources']:
                reponame = source.get('repo', source['name'])
                ref = source['ref']
                app.status(msg='Looking up sha1 for %(repo_name)s %(ref)s',
                           repo_name=reponame,
                           ref=ref)
                assert cache.has_repo(reponame)
                repo = cache.get_repo(reponame)
                source['ref'] = repo.resolve_ref(ref)

            self.write_morphology(filename, morph)

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

        if len(args) not in [1, 2]:
            raise cliapp.AppException('morph branch needs name of branch '
                                      'as parameter')

        new_branch = args[0]
        commit = 'master' if len(args) == 1 else args[1]

        # Create the system branch directory.
        os.makedirs(new_branch)

        # Create a .morph-system-branch directory to clearly identify
        # this directory as a morph system branch.
        os.mkdir(os.path.join(new_branch, '.morph-system-branch'))

        # Clone into system branch directory.
        new_repo = os.path.join(new_branch, self.system_repo_base)
        self.clone_to_directory(self.app, new_repo, self.system_repo_name,
                                commit)

        # Create a new branch in the local morphs repository.
        self.app.runcmd(['git', 'checkout', '-b', new_branch, commit],
                        cwd=new_repo)

    def checkout(self, args):
        '''Check out an existing system branch.'''

        if len(args) != 1:
            raise cliapp.AppException('morph checkout needs name of '
                                      'branch as parameter')

        system_branch = args[0]

        # Create the system branch directory.
        os.makedirs(system_branch)

        # Create a .morph-system-branch directory to clearly identify
        # this directory as a morph system branch.
        os.mkdir(os.path.join(system_branch, '.morph-system-branch'))

        # Clone into system branch directory.
        new_repo = os.path.join(system_branch, self.system_repo_base)
        self.clone_to_directory(self.app, new_repo, self.system_repo_name,
                                system_branch)

    def show_system_branch(self, args):
        '''Print name of current system branch.'''

        self.app.output.write('%s\n' % self.deduce_system_branch())

    def merge(self, args):
        '''Merge specified repositories from another system branch.'''

        if len(args) == 0:
            raise cliapp.AppException('morph merge must get a branch name '
                                      'and some repo names as arguments')

        app = self.app
        other_branch = args[0]
        workspace = self.deduce_workspace()
        this_branch = self.deduce_system_branch()

        for repo in args[1:]:
            repo = self.resolve_reponame(app, repo)
            basename = os.path.basename(repo)
            pull_from = os.path.join(workspace, other_branch, basename)
            repo_dir = os.path.join(workspace, this_branch, basename)
            app.runcmd(['git', 'pull', pull_from, other_branch], cwd=repo_dir)

    def edit(self, args):
        '''Edit a component in a system branch.'''

        if len(args) not in (1, 2):
            raise cliapp.AppException('morph edit must get a repository name '
                                      'and commit ref as argument')

        app = self.app
        workspace = self.deduce_workspace()
        system_branch = self.deduce_system_branch()

        morphs_dirname = os.path.join(workspace, system_branch, 'morphs')
        if morphs_dirname is None:
            raise morphlib.Error('Can not find morphs directory')

        repo = self.resolve_reponame(app, args[0])

        if len(args) == 2:
            ref = args[1]
        else:
            ref = self.find_edit_ref(app, morphs_dirname, repo)
            if ref is None:
                raise morphlib.Error('Cannot deduce commit to start edit from')

        new_repo = os.path.join(workspace, system_branch,
                                os.path.basename(repo))
        self.clone_to_directory(app, new_repo, args[0], ref)

        if system_branch == ref:
            app.runcmd(['git', 'checkout', system_branch],
                       cwd=new_repo)
        else:
            app.runcmd(['git', 'checkout', '-b', system_branch, ref],
                       cwd=new_repo)

        for filename, morph in self.morphs_for_repo(app, morphs_dirname, repo):
            changed = False
            for spec in morph['sources']:
                spec_repo = self.resolve_reponame(app, spec['repo'])
                if spec_repo == repo and spec['ref'] != system_branch:
                    app.status(msg='Replacing ref "%(ref)s" with "%(branch)s"'
                                   'in %(filename)s',
                               ref=spec['ref'], branch=system_branch,
                               filename=filename, chatty=True)
                    spec['ref'] = system_branch
                    changed = True
            if changed:
                self.write_morphology(filename, morph)
