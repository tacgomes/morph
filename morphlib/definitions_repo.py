# Copyright (C) 2015  Codethink Limited
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


'''Handles the Git repository containing Baserock definitions.'''


import cliapp

import contextlib
import logging
import os
import urlparse
import uuid

import morphlib
import gitdir


class DefinitionsRepoNotFound(cliapp.AppException):
    def __init__(self):
        cliapp.AppException.__init__(self,
            'This command must be run from inside a Git repository '
            'containing Baserock definitions.')


class FileOutsideRepo(cliapp.AppException):
    def __init__(self, path, repo):
        cliapp.AppException.__init__(self,
            'File %s is not in repo %s.' % (path, repo))


class DefinitionsRepo(gitdir.GitDirectory):
    '''Represents a definitions.git repo checked out locally.

    This can either be a normal Git clone, or a Git clone inside an old-style
    Morph workspace.

    If the repo is inside a Morph workspace, certain behaviours are enabled for
    consistency with old versions of Morph. See function documentation for
    details.

    '''
    def __init__(self, path, search_for_root=False, system_branch=None,
                 allow_missing=False):
        morphlib.gitdir.GitDirectory.__init__(
            self, path, search_for_root=search_for_root,
            allow_missing=allow_missing)
        self.system_branch = system_branch

    @property
    def HEAD(self):
        '''Return the ref considered to be HEAD of this definitions repo.

        In a normal Git checkout, this will return whatever ref is checked out
        as the working tree (HEAD, in Git terminology).

        If this definitions repo is in an old-style Morph system branch, it
        will return the ref that was checked out with `morph branch` or `morph
        checkout`, which will NOT necessarily correspond to what is checked out
        in the Git repo.

        '''
        if self.system_branch is None:
            return morphlib.gitdir.GitDirectory.HEAD.fget(self)
        else:
            return self.system_branch.get_config('branch.name')

    @property
    def remote_url(self):
        '''Return the 'upstream' URL of this repo.

        If this repo is inside a Morph system branch checkout, this will be
        whatever URL was passed to `morph checkout` or `morph branch`. That may
        be a keyed URL such as baserock:baserock/definitions.

        Otherwise, the fetch URL of the 'origin' remote is returned.

        '''
        if self.system_branch is None:
            return self.get_remote('origin').get_fetch_url()
        else:
            return self.system_branch.root_repository_url

    def branch_with_local_changes(self, uuid, push=True, build_ref_prefix=None,
                                  git_user_name=None, git_user_email=None,
                                  status_cb=None):
        '''Yield a branch that includes the user's local changes to this repo.

        When operating on local repos, this isn't really necessary. But when
        doing distributed building, any local changes the user has made need
        to be pushed. As a convenience for the user, Morph supports creating
        temporary branches with their local changes and pushing them to the
        'origin' remote of the repo they are working in.

        If there are no local changes, there is no temporary branch created,
        and the function yields whatever branch was checked out.

        The 'git_user_name' and 'git_user_email' parameters are used when
        creating commits in the temporary branch. The 'build_ref_prefix' is
        prepended to the ref name of the temporary branch. Pushing is limited
        to only certain refs in some Git servers.

        '''
        if status_cb:
            status_cb(msg='Looking for uncommitted changes (pass '
                          '--local-changes=ignore to skip)')

        if self.system_branch:
            bb = morphlib.buildbranch.BuildBranch(
                build_ref_prefix, uuid, system_branch=self.system_branch)
        else:
            bb = morphlib.buildbranch.BuildBranch(
                build_ref_prefix, uuid, definitions_repo=self)

        loader = morphlib.morphloader.MorphologyLoader()
        pbb = morphlib.buildbranch.pushed_build_branch(
            bb, loader=loader,
            changes_need_pushing=push, name=git_user_name,
            email=git_user_email, build_uuid=uuid,
            status=status_cb)
        return pbb   # (repo_url, commit, original_ref)

    @contextlib.contextmanager
    def source_pool(self, lrc, rrc, cachedir, ref, system_filename,
                    include_local_changes=False, push_local_changes=False,
                    update_repos=True, status_cb=None, build_ref_prefix=None,
                    git_user_name=None, git_user_email=None):
        '''Load the system defined in 'morph' and all the sources it contains.

        This is a context manager, because depending on the settings given it
        may create and push a temporary build branch. This is useful when there
        are local changes that you would like distributed build workers to
        build.

        If 'include_local_changes' is False, the on-disk definitions.git repo
        is used only to query the HEAD ref. Morph then looks for this ref in
        its local clone of that repo's 'origin' remote, which ensures that the
        changes it is building are pushed to the configured Git server (at
        least at time it is building them).

        When 'include_local_changes' is True, Morph will create a temporary
        branch in the repo including any local changes. If the definitions.git
        repo is inside an old-style Morph system branch, it will create
        temporary branches in all repos that have been marked with `morph
        edit`.  The branch is cleaned up when the context manager exits. The
        'user_name', 'user_email' and 'build_ref_prefix' settings must be
        passed if a temporary build branch is created.

        FIXME: if not inside an old-style Morph system branch, the temporary
        branch is redundant as Morph could just read the files from the disk
        as-is. This requires changes to SourceResolver before it is possible.

        The 'push_local_changes' option isn't much use. You probably want to
        use branch_with_local_changes() instead. It is present so that the
        `morph build` command continues to honour the 'push-build-branches'
        setting, but that was probably only useful for `morph distbuild` and
        that now uses branch_with_local_changes().

        The 'lrc' and 'rrc' parameters are local and remote Git repo caches.
        Use morphlib.util.new_repo_caches() to obtain these. The 'cachedir'
        parameter points to where Git repos are cached by Morph,
        app.settings['cachedir'] tells you that.

        The 'update_repos' flag allows you to disable updating Git repos, to
        honour app.settings['no-git-update']. If one of the refs in the build
        graph is not available locally and update_repos is False, you will see
        a morphlib.gitdir.InvalidRefError exception.

        The 'status_cb' function will be called if set to output progress and
        status messages to the user.

        The function yields a morphlib.srcpool.SourcePool instance, which is
        all you need to resolve cache keys, and construct a usable build graph.
        See morphlib.buildcommand.BuildCommand.resolve_artifacts() for a way
        of doing this.

        '''
        # FIXME: currently the way this function is implemented causes the
        # `deploy` command to re-create a temporary build branch for each
        # system that is deployed. This is a regression in terms of
        # performance. But it seems to me that the sourcepool object should
        # be able to contain multiple systems, and so the correct fix is to
        # extend this function to handle multiple systems, rather than split
        # up the 'process local changes' stage from the 'create source pool'
        # stage.
        if include_local_changes:
            build_uuid = uuid.uuid4().hex
            temporary_branch = DefinitionsRepo.branch_with_local_changes(
                self, build_uuid, push=push_local_changes,
                build_ref_prefix=build_ref_prefix, git_user_name=git_user_name,
                git_user_email=git_user_email, status_cb=status_cb)
            with temporary_branch as (repo_url, commit, original_ref):
                if status_cb:
                    status_cb(msg='Deciding on task order')

                yield morphlib.sourceresolver.create_source_pool(
                    lrc, rrc, repo_url, commit, [system_filename],
                    cachedir=cachedir, original_ref=original_ref,
                    update_repos=update_repos, status_cb=status_cb)
        else:
            repo_url = self.remote_url
            commit = self.resolve_ref_to_commit(ref)

            if status_cb:
                status_cb(msg='Deciding on task order')

            try:
                yield morphlib.sourceresolver.create_source_pool(
                    lrc, rrc, repo_url, commit, [system_filename],
                    cachedir=cachedir, original_ref=ref,
                    update_repos=update_repos, status_cb=status_cb)
            except morphlib.sourceresolver.InvalidDefinitionsRefError as e:
                raise cliapp.AppException(
                    'Commit %s wasn\'t found in the "origin" remote %s. '
                    'You either need to push your local commits on branch %s '
                    'to "origin", or use the --local-changes=include feature '
                    'of Morph.' % (e.ref, e.repo_url, ref))

    def load_all_morphologies(self, loader):
        mf = morphlib.morphologyfinder.MorphologyFinder(self)
        for filename in (f for f in mf.list_morphologies()
                         if not self.is_symlink(f)):
            text = mf.read_morphology(filename)
            m = loader.load_from_string(text, filename=filename)
            m.repo_url = self.remote_url
            m.ref = self.HEAD
            yield m

    def relative_path(self, path, cwd='.'):
        '''Make 'path' relative to the top directory of this repo.

        If 'path' is a relative path, it is taken to be relative to the
        current working directory. Thus, the result of this function will
        be different depending on the value of os.getcwd().

        If the given path is outside the repo, a PathOutsideRepo exception
        is raised.

        '''
        def path_is_outside_repo(path):
            return path.split(os.sep, 1)[0] == '..'

        absolute_path = os.path.join(cwd, os.path.abspath(path))
        repo_relative_path = os.path.relpath(absolute_path, self.dirname)

        if path_is_outside_repo(repo_relative_path):
            raise FileOutsideRepo(repo_relative_path, self)

        return repo_relative_path

    def relative_path_to_chunk(self, repo_url):
        '''Return a sensible directory to check out repo_url.

        This will be a path in the directory that contains this definitions
        repo, with its name based on 'repo_url'.

        '''
        # This is copied from systembranch._fabricate_git_directory_name().

        # Parse the URL. If the path component is absolute, we assume
        # it's a real URL; otherwise, an aliased URL.
        parts = urlparse.urlparse(repo_url)

        if os.path.isabs(parts.path):
            # Remove .git suffix, if any.
            path = parts.path
            if path.endswith('.git'):
                path = path[:-len('.git')]

            # Add the domain name etc (netloc). Ignore any other parts.
            # Note that we _know_ the path starts with a slash, so we avoid
            # adding one here.
            relative = '%s%s' % (parts.netloc, path)
        else:
            relative = repo_url

        # Replace colons with slashes.
        relative = '/'.join(relative.split(':'))

        # Remove anyleading slashes, or os.path.join below will only
        # use the relative part (since it's absolute, not relative).
        relative = relative.lstrip('/')

        return os.path.join(os.path.dirname(self.dirname), relative)


class DefinitionsRepoWithApp(DefinitionsRepo):
    '''Wrapper class for DefinitionsRepo that understands Morph settings.

    The DefinitionsRepo class does not require a morphlib.app.Application
    instance to use it. However, this means you need to pass quite a lot
    of parameters in. Code inside Morph can use this class instead to save
    duplicating code.

    '''
    def __init__(self, app, *args, **kwargs):
        DefinitionsRepo.__init__(self, *args, **kwargs)
        self.app = app

        self._git_user_name = morphlib.git.get_user_name(app.runcmd)
        self._git_user_email = morphlib.git.get_user_email(app.runcmd)

        self._lrc, self._rrc = morphlib.util.new_repo_caches(app)

    def branch_with_local_changes(self, uuid, push=False):
        '''Equivalent to DefinitionsRepo.branch_with_local_changes().'''

        return DefinitionsRepo.branch_with_local_changes(
            self, uuid,
            push=(push or self.app.settings['push-build-branches']),
            build_ref_prefix=self.app.settings['build-ref-prefix'],
            git_user_name=self._git_user_name,
            git_user_email=self._git_user_email,
            status_cb=self.app.status,)

    def source_pool(self, ref, system_filename):
        '''Equivalent to DefinitionsRepo.source_pool().'''

        local_changes = self.app.settings['local-changes']
        return DefinitionsRepo.source_pool(
            self, self._lrc, self._rrc, self.app.settings['cachedir'],
            ref, system_filename,
            include_local_changes=(local_changes == 'include'),
            push_local_changes=self.app.settings['push-build-branches'],
            build_ref_prefix=self.app.settings['build-ref-prefix'],
            git_user_name=self._git_user_name,
            git_user_email=self._git_user_email,
            status_cb=self.app.status,
            update_repos=(not self.app.settings['no-git-update']))


def _system_branch(path):
    '''Open an old-style Morph system branch in an old-style Morph workspace.

    Raises morphlib.workspace.NotInWorkspace or
    morphlib.sysbranchdir.NotInSystemBranch if either workspace or
    system-branch are not found.

    '''
    morphlib.workspace.open(path)
    system_branch = morphlib.sysbranchdir.open_from_within(path)
    return system_branch


def _local_definitions_repo(path, search_for_root, system_branch=None,
                            app=None):
    '''Open a local Git repo containing Baserock definitions, at 'path'.

    Raises morphlib.gitdir.NoGitRepoError if there is no repo found at 'path'.

    '''
    if app:
        gitdir = morphlib.definitions_repo.DefinitionsRepoWithApp(
            app, path, search_for_root=search_for_root,
            system_branch=system_branch)
    else:
        gitdir = morphlib.definitions_repo.DefinitionsRepo(
            path, search_for_root=search_for_root, system_branch=system_branch)
    return gitdir


def open(path, search_for_root=False, search_workspace=False, app=None):
    '''Open the definitions.git repo at 'path'.

    Returns a DefinitionsRepo instance.

    If 'search_for_root' is True, this function will traverse up from 'path'
    to find a .git directory, and assume that is the top of the Git repository.
    If you are trying to find the repo based on the current working directory,
    you should set this to True. If you are trying to find the repo based on a
    path entered manually by the user, you may want to set this to False to
    avoid confusion.

    If 'search_workspace' is True, this function will check if 'path' is inside
    an old-style Morph workspace. If it is, there will be two changes to its
    behaviour. First, the definitions.git will be returned even if 'path' is
    inside a different repo, because the old-style Morph system branch will
    identify which is the correct definitions.git repo. Second, the value
    returned for HEAD will not be the ref checked out in the definitions.git
    repo, but rather the ref that was passed to `morph checkout` or `morph
    branch` when the system branch was originally checked out. This behaviour
    may seem confusing if you are new to Morph, but in fact Morph forced users
    to work this way for several years, so we need preserve this behaviour for
    a while to avoid disrupting existing users.

    '''
    sb = None

    if search_workspace:
        try:
            sb = _system_branch(path)
        except (morphlib.workspace.NotInWorkspace,
                morphlib.sysbranchdir.NotInSystemBranch):
            logging.debug('Did not find old-style Morph system branch')

    if sb:
        path = sb.get_git_directory_name(sb.root_repository_url)
        definitions_repo = _local_definitions_repo(
            path=path, search_for_root=False, system_branch=sb, app=app)
        logging.info('Opened definitions repo %s from Morph system branch %s',
                     definitions_repo, sb)
    else:
        try:
            definitions_repo = _local_definitions_repo(
                path, search_for_root=search_for_root, app=app)
        except morphlib.gitdir.NoGitRepoError:
            raise DefinitionsRepoNotFound()
        logging.info('Opened definitions repo %s', definitions_repo)

    return definitions_repo
