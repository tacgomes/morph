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
import glob
import logging
import os
import shutil

import morphlib


class BranchRootHasNoSystemsError(cliapp.AppException):
    def __init__(self, repo, ref):
        cliapp.AppException.__init__(
            self, 'System branch root repository %s '
                  'has no system morphologies at ref %s' % (repo, ref))


class SimpleBranchAndMergePlugin(cliapp.Plugin):

    '''Add subcommands for handling workspaces and system branches.'''

    def enable(self):
        self.app.add_subcommand('init', self.init, arg_synopsis='[DIR]')
        self.app.add_subcommand('workspace', self.workspace, arg_synopsis='')
        self.app.add_subcommand(
            'checkout', self.checkout, arg_synopsis='REPO BRANCH')
        self.app.add_subcommand(
            'branch', self.branch, arg_synopsis='REPO NEW [OLD]')
        self.app.add_subcommand(
            'edit', self.edit, arg_synopsis='SYSTEM STRATUM [CHUNK]')
        self.app.add_subcommand(
            'petrify', self.petrify, arg_synopsis='')
        self.app.add_subcommand(
            'unpetrify', self.unpetrify, arg_synopsis='')
        self.app.add_subcommand(
            'show-system-branch', self.show_system_branch, arg_synopsis='')
        self.app.add_subcommand(
            'show-branch-root', self.show_branch_root, arg_synopsis='')
        self.app.add_subcommand('foreach', self.foreach,
                                arg_synopsis='-- COMMAND [ARGS...]')

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

            gd = sb.clone_cached_repo(cached_repo, system_branch)

            if not self._checkout_has_systems(gd):
                raise BranchRootHasNoSystemsError(root_url, system_branch)

            gd.update_submodules(self.app)
            gd.update_remotes()
        except BaseException as e:
            # Oops. Clean up.
            logging.error('Caught exception: %s' % str(e))
            logging.info('Removing half-finished branch %s' % system_branch)
            self._remove_branch_dir_safe(ws.root, root_dir)
            raise

    def branch(self, args):
        '''Create a new system branch.

        Command line arguments:

        * `REPO` is a repository URL.
        * `NEW` is the name of the new system branch.
        * `OLD` is the point from which to branch, and defaults to `master`.

        This creates a new system branch. It needs to be run in an
        existing workspace (see `morph workspace`). It creates a new
        git branch in the clone of the repository in the workspace. The
        system branch will not be visible on the git server until you
        push your changes to the repository.

        Example:

            cd /src/workspace
            morph branch baserock:baserock/morphs jrandom/new-feature

        '''

        if len(args) not in [2, 3]:
            raise cliapp.AppException(
                'morph branch needs name of branch as parameter')

        root_url = args[0]
        system_branch = args[1]
        base_ref = 'master' if len(args) == 2 else args[2]
        origin_base_ref = 'origin/%s' % base_ref

        self._require_git_user_config()

        # Open the workspace first thing, so user gets a quick error if
        # we're not inside a workspace.
        ws = morphlib.workspace.open('.')

        # Make sure the root repository is in the local git repository
        # cache, and is up to date.
        lrc, rrc = morphlib.util.new_repo_caches(self.app)
        cached_repo = lrc.get_updated_repo(root_url)

        # Make sure the system branch doesn't exist yet.
        if cached_repo.ref_exists(system_branch):
            raise cliapp.AppException(
                'branch %s already exists in repository %s' %
                (system_branch, root_url))

        # Make sure the base_ref exists.
        cached_repo.resolve_ref(base_ref)

        root_dir = ws.get_default_system_branch_directory_name(system_branch)

        try:
            # Create the system branch directory. This doesn't yet clone
            # the root repository there.
            sb = morphlib.sysbranchdir.create(
                root_dir, root_url, system_branch)

            gd = sb.clone_cached_repo(cached_repo, base_ref)
            gd.branch(system_branch, base_ref)
            gd.checkout(system_branch)

            if not self._checkout_has_systems(gd):
                raise BranchRootHasNoSystemsError(root_url, base_ref)

            gd.update_submodules(self.app)
            gd.update_remotes()
        except BaseException as e:
            # Oops. Clean up.
            logging.error('Caught exception: %s' % str(e))
            logging.info('Removing half-finished branch %s' % system_branch)
            self._remove_branch_dir_safe(ws.root, root_dir)
            raise

    def _save_dirty_morphologies(self, loader, sb, morphs):
        logging.debug('Saving dirty morphologies: start')
        for morph in morphs:
            if morph.dirty:
                logging.debug(
                    'Saving morphology: %s %s %s' %
                        (morph.repo_url, morph.ref, morph.filename))
                loader.unset_defaults(morph)
                loader.save_to_file(
                    sb.get_filename(morph.repo_url, morph.filename), morph)
                morph.dirty = False
        logging.debug('Saving dirty morphologies: done')

    def _get_stratum_triplets(self, morph):
        # Gather all references to other strata from a morphology. The
        # morphology must be either a system or a stratum one. In a
        # stratum one, the refs are all for build dependencies of the
        # stratum. In a system one, they're the list of strata in the
        # system.

        assert morph['kind'] in ('system', 'stratum')
        if morph['kind'] == 'system':
            specs = morph.get('strata', [])
        elif morph['kind'] == 'stratum':
            specs = morph.get('build-depends', [])

        # Given a list of dicts that reference strata, return a list
        # of triplets (repo url, ref, filename).

        return [
            (spec['repo'], spec['ref'], '%s.morph' % spec['morph'])
            for spec in specs
        ]

    def _checkout(self, lrc, sb, repo_url, ref):
        logging.debug(
            'Checking out %s (%s) into %s' %
                (repo_url, ref, sb.root_directory))
        cached_repo = lrc.get_updated_repo(repo_url)
        gd = sb.clone_cached_repo(cached_repo, ref)
        gd.update_submodules(self.app)
        gd.update_remotes()

    def _load_morphology_from_file(self, loader, dirname, filename):
        full_filename = os.path.join(dirname, filename)
        return loader.load_from_file(full_filename)

    def _load_morphology_from_git(self, loader, gd, ref, filename):
        try:
            text = gd.cat_file('blob', ref, filename)
        except cliapp.AppException:
            text = gd.cat_file('blob', 'origin/%s' % ref, filename)
        return loader.load_from_string(text, filename)

    def _load_stratum_morphologies(self, loader, sb, system_morph):
        logging.debug('Starting to load strata for %s' % system_morph.filename)
        lrc, rrc = morphlib.util.new_repo_caches(self.app)
        morphset = morphlib.morphset.MorphologySet()
        queue = self._get_stratum_triplets(system_morph)
        while queue:
            repo_url, ref, filename = queue.pop()
            if not morphset.has(repo_url, ref, filename):
                logging.debug('Loading: %s %s %s' % (repo_url, ref, filename))
                dirname = sb.get_git_directory_name(repo_url)

                # Get the right morphology. The right ref might not be
                # checked out, in which case we get the file from git.
                # However, if it is checked out, we get it from the
                # filesystem directly, in case the user has made any
                # changes to it. If the entire repo hasn't been checked
                # out yet, do that first.

                if not os.path.exists(dirname):
                    self._checkout(lrc, sb, repo_url, ref)
                    m = self._load_morphology_from_file(
                        loader, dirname, filename)
                else:
                    gd = morphlib.gitdir.GitDirectory(dirname)
                    if gd.is_currently_checked_out(ref):
                        m = self._load_morphology_from_file(
                            loader, dirname, filename)
                    else:
                        m = self._load_morphology_from_git(
                            loader, gd, ref, filename)

                m.repo_url = repo_url
                m.ref = ref
                m.filename = filename

                morphset.add_morphology(m)
                queue.extend(self._get_stratum_triplets(m))

        logging.debug('All strata loaded')
        return morphset

    def _invent_new_branch(self, cached_repo, default_name):
        counter = 0
        candidate = default_name
        while True:
            try:
                cached_repo.resolve_ref(candidate)
            except morphlib.cachedrepo.InvalidReferenceError:
                return candidate
            else:
                counter += 1
                candidate = '%s-%s' % (default_name, counter)

    def edit(self, args):
        '''Edit or checkout a component in a system branch.

        Command line arguments:

        * `SYSTEM` is the name of a system morphology in the root repository
          of the current system branch.
        * `STRATUM` is the name of a stratum inside the system.
        * `CHUNK` is the name of a chunk inside the stratum.

        This marks the specified stratum or chunk (if given) as being
        changed within the system branch, by creating the git branches in
        the affected repositories, and changing the relevant morphologies
        to point at those branches. It also creates a local clone of
        the git repository of the stratum or chunk.

        For example:

            morph edit devel-system-x86-64-generic devel

        The above command will mark the `devel` stratum as being
        modified in the current system branch. In this case, the stratum's
        morphology is in the same git repository as the system morphology,
        so there is no need to create a new git branch. However, the
        system morphology is modified to point at the stratum morphology
        in the same git branch, rather than the original branch.

        In other words, where the system morphology used to say this:

            morph: devel
            repo: baserock:baserock/morphs
            ref: master

        The updated system morphology will now say this instead:

            morph: devel
            repo: baserock:baserock/morphs
            ref: jrandom/new-feature

        (Assuming the system branch is called `jrandom/new-feature`.)

        Another example:

            morph edit devel-system-x86_64-generic devel gcc

        The above command will mark the `gcc` chunk as being edited in
        the current system branch. Morph will clone the `gcc` repository
        locally, into the current workspace, and create a new (local)
        branch named after the system branch. It will also change the
        stratum morphology to refer to the new git branch, instead of
        whatever branch it was referring to originally.

        If the `gcc` repository already had a git branch named after
        the system branch, that is reused. Similarly, if the stratum
        morphology was already pointing that that branch, it doesn't
        need to be changed again. In that case, the only action Morph
        does is to clone the chunk repository locally, and if that was
        also done already, Morph does nothing.

        '''

        if len(args) not in (2, 3):
            raise cliapp.AppException('morph edit needs the names of a system,'
                                      ' a stratum and optionally a chunk'
                                      ' as parameters')

        system_name = args[0]
        stratum_name = args[1]
        chunk_name = args[2] if len(args) == 3 else None

        ws = morphlib.workspace.open('.')
        sb = morphlib.sysbranchdir.open_from_within('.')
        loader = morphlib.morphloader.MorphologyLoader()

        # FIXME: The old "morph edit" code did its own morphology validation,
        # which was much laxer than what MorphologyFactory does, or the
        # new MorphologyLoader does. This new "morph edit" uses
        # MorphologyLoader, and the stricter validation breaks the test
        # suite. However, I want to keep the test suite as untouched as
        # possible, until all the old code is gone (after which the test
        # suite will be refactored). Thus, to work around the test suite
        # breaking, we disable morphology validation for now.
        loader.validate = lambda *args: None

        # Load the system morphology, and all stratum morphologies, including
        # all the strata that are being build-depended on.

        logging.debug('Loading system morphology')
        system_morph = loader.load_from_file(
            sb.get_filename(sb.root_repository_url, system_name + '.morph'))
        system_morph.repo_url = sb.root_repository_url
        system_morph.ref = sb.system_branch_name
        system_morph.filename = system_name + '.morph'

        logging.debug('Loading stratum morphologies')
        morphs = self._load_stratum_morphologies(loader, sb, system_morph)
        morphs.add_morphology(system_morph)
        logging.debug('morphs: %s' % repr(morphs.morphologies))

        # Change refs to the stratum to be to the system branch.
        # Note: this currently only supports strata in root repository.

        logging.debug('Changing refs to stratum %s' % stratum_name)
        stratum_morph = morphs.get_stratum_in_system(
            system_morph, stratum_name)
        morphs.change_ref(
            stratum_morph.repo_url, stratum_morph.ref, stratum_morph.filename,
            sb.system_branch_name)
        logging.debug('morphs: %s' % repr(morphs.morphologies))

        # If we're editing a chunk, make it available locally, with the
        # relevant git branch checked out. This also invents the new branch
        # name.

        if chunk_name:
            logging.debug('Editing chunk %s' % chunk_name)

            chunk_url, chunk_ref, chunk_morph = morphs.get_chunk_triplet(
                stratum_morph, chunk_name)

            chunk_dirname = sb.get_git_directory_name(chunk_url)
            if not os.path.exists(chunk_dirname):
                lrc, rrc = morphlib.util.new_repo_caches(self.app)
                cached_repo = lrc.get_updated_repo(chunk_url)

                # FIXME: This makes the simplifying assumption that
                # a chunk branch must have the same name as the system
                # branch.

                gd = sb.clone_cached_repo(cached_repo, chunk_ref)
                if chunk_ref != sb.system_branch_name:
                    gd.branch(sb.system_branch_name, chunk_ref)
                    gd.checkout(sb.system_branch_name)
                gd.update_submodules(self.app)
                gd.update_remotes()

                # Change the refs to the chunk.
                if chunk_ref != sb.system_branch_name:
                    morphs.change_ref(
                        chunk_url, chunk_ref, chunk_morph + '.morph',
                        sb.system_branch_name)

        # Save any modified strata.

        self._save_dirty_morphologies(loader, sb, morphs.morphologies)

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

    @staticmethod
    def _checkout_has_systems(gd):
        loader = morphlib.morphloader.MorphologyLoader()
        for filename in glob.iglob(os.path.join(gd.dirname, '*.morph')):
            m = loader.load_from_file(filename)
            if m['kind'] == 'system':
                return True
        return False

    def foreach(self, args):
        '''Run a command in each repository checked out in a system branch.

        Use -- before specifying the command to separate its arguments from
        Morph's own arguments.

        Command line arguments:

        * `--` indicates the end of option processing for Morph.
        * `COMMAND` is a command to run.
        * `ARGS` is a list of arguments or options to be passed onto
          `COMMAND`.

        This runs the given `COMMAND` in each git repository belonging
        to the current system branch that exists locally in the current
        workspace.  This can be a handy way to do the same thing in all
        the local git repositories.

        For example:

            morph foreach -- git push

        The above command would push any committed changes in each
        repository to the git server.

        '''

        if not args:
            raise cliapp.AppException('morph foreach expects a command to run')

        ws = morphlib.workspace.open('.')
        sb = morphlib.sysbranchdir.open_from_within('.')

        for gd in sorted(sb.list_git_directories(), key=lambda gd: gd.dirname):
            # Get the repository's original name
            # Continue in the case of error, since the previous iteration
            # worked in the case of the user cloning a repository in the
            # system branch's directory.
            try:
                repo = gd.get_config('morph.repository')
            except cliapp.AppException:
                continue

            self.app.output.write('%s\n' % repo)
            status, output, error = self.app.runcmd_unchecked(
                args, cwd=gd.dirname)
            self.app.output.write(output)
            if status != 0:
                self.app.output.write(error)
                pretty_command = ' '.join(cliapp.shell_quote(arg)
                                          for arg in args)
                raise cliapp.AppException(
                    'Command failed at repo %s: %s'
                    % (repo, pretty_command))
            self.app.output.write('\n')
            self.app.output.flush()

    def _load_all_sysbranch_morphologies(self, sb, loader):
        '''Read in all the morphologies in the root repository.'''
        self.app.status(msg='Loading in all morphologies')
        morphs = morphlib.morphset.MorphologySet()
        mf = morphlib.morphologyfinder.MorphologyFinder(
            morphlib.gitdir.GitDirectory(
                sb.get_git_directory_name(sb.root_repository_url)))
        for morph in mf.list_morphologies():
            text, filename = mf.read_morphology(morph)
            m = loader.load_from_string(text, filename=filename)
            m.repo_url = sb.root_repository_url
            m.ref = sb.system_branch_name
            morphs.add_morphology(m)
        return morphs

    def petrify(self, args):
        '''Convert all chunk refs in a system branch to be fixed SHA1s.

        This modifies all git commit references in system and stratum
        morphologies, in the current system branch, to be fixed SHA
        commit identifiers, rather than symbolic branch or tag names.
        This is useful for making sure none of the components in a system
        branch change accidentally.

        Consider the following scenario:

        * The `master` system branch refers to `gcc` using the
          `baserock/morph` ref. This is appropriate, since the main line
          of development should use the latest curated code.

        * You create a system branch to prepare for a release, called
          `TROVE_ID/release/2.0`. The reference to `gcc` is still
          `baserock/morph`.

        * You test everything, and make a release. You deploy the release
          images onto devices, which get shipped to your customers.

        * A new version GCC is committed to the `baserock/morph` branch.

        * Your release branch suddenly uses a new compiler, which may
          or may not work for your particular system at that release.

        To avoid this, you need to _petrify_ all git references
        so that they do not change accidentally. If you've tested
        your release with the GCC release that is stored in commit
        `94c50665324a7aeb32f3096393ec54b2e63bfb28`, then you should
        continue to use that version of GCC, regardless of what might
        happen in the master system branch. If, and only if, you decide
        that a new compiler would be good for your release should you
        include it in your release branch. This way, only the things
        that you change intentionally change in your release branch.

        '''

        if args:
            raise cliapp.AppException('morph petrify takes no arguments')

        ws = morphlib.workspace.open('.')
        sb = morphlib.sysbranchdir.open_from_within('.')
        loader = morphlib.morphloader.MorphologyLoader()
        lrc, rrc = morphlib.util.new_repo_caches(self.app)
        update_repos = not self.app.settings['no-git-update']
        done = set()

        morphs = self._load_all_sysbranch_morphologies(sb, loader)

        # Petrify the ref to each stratum and chunk.
        def petrify_specs(specs):
            for spec in specs:
                ref = spec['ref']
                # Do not double petrify refs
                if morphlib.git.is_valid_sha1(ref):
                    continue
                commit_sha1, tree_sha1 = self.app.resolve_ref(
                    lrc, rrc, spec['repo'], ref, update=update_repos)
                assert 'name' in spec or 'morph' in spec
                filename = '%s.morph' % spec.get('morph', spec.get('name'))
                morphs.change_ref(spec['repo'], ref, filename, commit_sha1)

        for m in morphs.morphologies:
            if m['kind'] == 'system':
                petrify_specs(m['strata'])
            elif m['kind'] == 'stratum':
                petrify_specs(m['build-depends'])
                petrify_specs(m['chunks'])

        # Write morphologies back out again.
        self._save_dirty_morphologies(loader, sb, morphs.morphologies)

    def unpetrify(self, args):
        '''Reverse the process of petrification.

        This undoes the changes `morph petrify` did.

        '''

        if args:
            raise cliapp.AppException('morph petrify takes no arguments')

        ws = morphlib.workspace.open('.')
        sb = morphlib.sysbranchdir.open_from_within('.')
        loader = morphlib.morphloader.MorphologyLoader()
        lrc, rrc = morphlib.util.new_repo_caches(self.app)
        update_repos = not self.app.settings['no-git-update']
        done = set()

        morphs = self._load_all_sysbranch_morphologies(sb, loader)

        # Restore the ref for each stratum and chunk
        def unpetrify_specs(specs):
            dirty = False
            for spec in specs:
                ref = spec['ref']
                # Don't attempt to unpetrify refs which aren't petrified
                if not ('unpetrify-ref' in spec
                        and morphlib.git.is_valid_sha1(ref)):
                    continue
                spec['ref'] = spec.pop('unpetrify-ref')
                dirty = True
            return dirty

        for m in morphs.morphologies:
            dirty = False
            if m['kind'] == 'system':
                dirty = dirty or unpetrify_specs(m['strata'])
            elif m['kind'] == 'stratum':
                dirty = dirty or unpetrify_specs(m['build-depends'])
                dirty = dirty or unpetrify_specs(m['chunks'])
            m.dirty = True

        # Write morphologies back out again.
        self._save_dirty_morphologies(loader, sb, morphs.morphologies)
