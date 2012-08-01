# Copyright (C) 2011-2012  Codethink Limited
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
import collections
import glob
import json
import logging
import os
import shutil
import tempfile
import time
import warnings

import morphlib


defaults = {
    'repo-alias': [
        ('upstream='
            'git://roadtrain.codethink.co.uk/delta/#'
            'gitano@roadtrain.codethink.co.uk:delta/'),
        ('baserock='
            'git://roadtrain.codethink.co.uk/baserock/#'
            'gitano@roadtrain.codethink.co.uk:baserock/'),
        ('freedesktop='
            'git://anongit.freedesktop.org/#'
            'ssh://git.freedesktop.org/'),
        ('gnome='
            'git://git.gnome.org/%s#'
            'ssh://git.gnome.org/git/%s'),
        ('github='
            'git://github.com/%s#'
            'git@github.com:%s'),
    ],
    'cachedir': os.path.expanduser('~/.cache/morph'),
    'max-jobs': morphlib.util.make_concurrency(),
    'prefix': '/usr',
    'toolchain-target': '%s-baserock-linux-gnu' % os.uname()[4],
    'ccache-remotedir': '',
    'ccache-remotenlevels': 2,
}


class BuildCommand(object):

    '''High level logic for building.

    This controls how the whole build process goes. This is a separate
    class to enable easy experimentation of different approaches to
    the various parts of the process.

    '''

    def __init__(self, app):
        self.app = app
        self.build_env = self.new_build_env()
        self.ckc = self.new_cache_key_computer(self.build_env)
        self.lac, self.rac = self.new_artifact_caches()
        self.lrc, self.rrc = self.new_repo_caches()

    def build(self, args):
        '''Build triplets specified on command line.'''

        self.app.status(msg='Build starts', chatty=True)

        for repo_name, ref, filename in self.app.itertriplets(args):
            self.app.status(msg='Building %(repo_name)s %(ref)s %(filename)s',
                            repo_name=repo_name, ref=ref, filename=filename)
            order = self.compute_build_order(repo_name, ref, filename)
            self.build_in_order(order)

        self.app.status(msg='Build ends successfully', chatty=True)

    def new_build_env(self):
        '''Create a new BuildEnvironment instance.'''
        return morphlib.buildenvironment.BuildEnvironment(self.app.settings)

    def new_cache_key_computer(self, build_env):
        '''Create a new cache key computer.'''
        return morphlib.cachekeycomputer.CacheKeyComputer(build_env)

    def new_artifact_caches(self):
        return morphlib.util.new_artifact_caches(self.app.settings)

    def create_artifact_cachedir(self):
        return morphlib.util.create_artifact_cachedir(self.app.settings)

    def new_repo_caches(self):
        return morphlib.util.new_repo_caches(self.app)

    def create_cachedir(self):
        return morphlib.util.create_cachedir(self.app.settings)

    def compute_build_order(self, repo_name, ref, filename):
        '''Compute build order for a triplet.'''
        self.app.status(msg='Figuring out the right build order')

        self.app.status(msg='Creating source pool', chatty=True)
        srcpool = self.app.create_source_pool(
            self.lrc, self.rrc, (repo_name, ref, filename))

        self.app.status(msg='Creating artifact resolver', chatty=True)
        ar = morphlib.artifactresolver.ArtifactResolver()

        self.app.status(msg='Resolving artifacts', chatty=True)
        artifacts = ar.resolve_artifacts(srcpool)

        self.app.status(msg='Computing cache keys', chatty=True)
        for artifact in artifacts:
            artifact.cache_key = self.ckc.compute_key(artifact)
            artifact.cache_id = self.ckc.get_cache_id(artifact)

        self.app.status(msg='Computing build order', chatty=True)
        order = morphlib.buildorder.BuildOrder(artifacts)

        return order

    def build_in_order(self, order):
        '''Build everything specified in a build order.'''
        self.app.status(msg='Building according to build ordering',
                        chatty=True)
        for group in order.groups:
            self.build_artifacts(group)

    def build_artifacts(self, artifacts):
        '''Build a set of artifact.

        Typically, this would be a build group, but might be anything.
        At this level of abstraction we don't care.

        '''

        self.app.status(msg='Building a set of artifacts', chatty=True)
        for artifact in artifacts:
            self.build_artifact(artifact)

    def build_artifact(self, artifact):
        '''Build one artifact.

        All the dependencies are assumed to be built and available
        in either the local or remote cache already.

        '''

        self.app.status(msg='Checking if %(kind)s %(name)s needs building',
                        kind=artifact.source.morphology['kind'],
                        name=artifact.name)

        if self.is_built(artifact):
            self.app.status(msg='The %(kind)s %(name)s is already built',
                            kind=artifact.source.morphology['kind'],
                            name=artifact.name)
        else:
            self.app.status(msg='Building %(kind)s %(name)s',
                            kind=artifact.source.morphology['kind'],
                            name=artifact.name)
            self.get_sources(artifact)
            deps = self.get_recursive_deps(artifact)
            self.cache_artifacts_locally(deps)
            staging_area = self.create_staging_area(artifact)
            if self.app.settings['staging-chroot']:
                if artifact.source.morphology.needs_staging_area:
                    self.install_fillers(staging_area)
                    self.install_chunk_artifacts(staging_area,
                                                 deps)
            self.build_and_cache(staging_area, artifact)
            if self.app.settings['bootstrap']:
                self.install_chunk_artifacts(staging_area,
                                             (artifact,))
            self.remove_staging_area(staging_area)

    def is_built(self, artifact):
        '''Does either cache already have the artifact?'''
        return self.lac.has(artifact) or (self.rac and self.rac.has(artifact))

    def get_recursive_deps(self, artifact):
        done = set()
        todo = set((artifact,))
        while todo:
            for a in todo.pop().dependencies:
                if a not in done:
                    done.add(a)
                    todo.add(a)
        return done

    def get_sources(self, artifact):
        '''Update the local git repository cache with the sources.'''

        repo_name = artifact.source.repo_name
        if self.app.settings['no-git-update']:
            self.app.status(msg='Not updating existing git repository '
                                '%(repo_name)s '
                                'because of no-git-update being set',
                            chatty=True,
                            repo_name=repo_name)
            artifact.source.repo = self.lrc.get_repo(repo_name)
            return

        if self.lrc.has_repo(repo_name):
            artifact.source.repo = self.lrc.get_repo(repo_name)
            try:
                sha1 = artifact.source.sha1
                artifact.source.repo.resolve_ref(sha1)
                self.app.status(msg='Not updating git repository '
                                    '%(repo_name)s because it '
                                    'already contains sha1 %(sha1)s',
                                chatty=True, repo_name=repo_name,
                                sha1=sha1)
            except morphlib.cachedrepo.InvalidReferenceError:
                self.app.status(msg='Updating %(repo_name)s',
                                repo_name=repo_name)
                artifact.source.repo.update()
        else:
            self.app.status(msg='Cloning %(repo_name)s',
                            repo_name=repo_name)
            artifact.source.repo = self.lrc.cache_repo(repo_name)

        # Update submodules.
        done = set()
        self.app.cache_repo_and_submodules(
            self.lrc, artifact.source.repo.url,
            artifact.source.sha1, done)

    def cache_artifacts_locally(self, artifacts):
        '''Get artifacts missing from local cache from remote cache.'''

        def copy(remote, local):
            shutil.copyfileobj(remote, local)
            remote.close()
            local.close()

        for artifact in artifacts:
            if not self.lac.has(artifact):
                self.app.status(msg='Fetching to local cache: '
                                    'artifact %(name)s',
                                name=artifact.name)
                copy(self.rac.get(artifact), self.lac.put(artifact))

            if artifact.source.morphology.needs_artifact_metadata_cached:
                if not self.lac.has_artifact_metadata(artifact, 'meta'):
                    self.app.status(msg='Fetching to local cache: '
                                        'artifact metadata %(name)s',
                                    name=artifact.name)
                    copy(self.rac.get_artifact_metadata(artifact, 'meta'),
                         self.lac.put_artifact_metadata(artifact, 'meta'))

    def create_staging_area(self, artifact):
        '''Create the staging area for building a single artifact.'''

        if self.app.settings['staging-chroot']:
            staging_root = tempfile.mkdtemp(dir=self.app.settings['tempdir'])
            staging_temp = staging_root
        else:
            staging_root = '/'
            staging_temp = tempfile.mkdtemp(dir=self.app.settings['tempdir'])

        self.app.status(msg='Creating staging area')
        staging_area = morphlib.stagingarea.StagingArea(self.app,
                                                        staging_root,
                                                        staging_temp)
        return staging_area

    def remove_staging_area(self, staging_area):
        '''Remove the staging area.'''

        if staging_area.dirname != '/':
            self.app.status(msg='Removing staging area')
            staging_area.remove()
        temp_path = staging_area.tempdir
        if temp_path != '/' and os.path.exists(temp_path):
            self.app.status(msg='Removing temporary staging directory')
            shutil.rmtree(temp_path)

    def install_fillers(self, staging_area):
        '''Install staging fillers into the staging area.

        This must not be called in bootstrap mode.

        '''

        logging.debug('Pre-populating staging area %s' % staging_area.dirname)
        logging.debug('Fillers: %s' %
                      repr(self.app.settings['staging-filler']))
        for filename in self.app.settings['staging-filler']:
            with open(filename, 'rb') as f:
                self.app.status(msg='Installing %(filename)s',
                                filename=filename)
                staging_area.install_artifact(f)

    def install_chunk_artifacts(self, staging_area, artifacts):
        '''Install chunk artifacts into staging area.

        We only ever care about chunk artifacts as build dependencies,
        so this is not a generic artifact installer into staging area.
        Any non-chunk artifacts are silently ignored.

        All artifacts MUST be in the local artifact cache already.

        '''

        for artifact in artifacts:
            if artifact.source.morphology['kind'] != 'chunk':
                continue
            self.app.status(msg='Installing chunk %(chunk_name)s',
                            chunk_name=artifact.name)
            handle = self.lac.get(artifact)
            staging_area.install_artifact(handle)

    def build_and_cache(self, staging_area, artifact):
        '''Build an artifact and put it into the local artifact cache.'''

        self.app.status(msg='Starting actual build')
        setup_mounts = self.app.settings['staging-chroot']
        builder = morphlib.builder2.Builder(
            self.app, staging_area, self.lac, self.rac, self.lrc,
            self.build_env, self.app.settings['max-jobs'], setup_mounts)
        return builder.build_and_cache(artifact)


class Morph(cliapp.Application):

    def add_settings(self):
        self.settings.boolean(['verbose', 'v'],
                              'show what is happening in much detail')
        self.settings.boolean(['quiet', 'q'],
                              'show no output unless there is an error')
        self.settings.string_list(['repo-alias'],
                                  'define URL prefix aliases to allow '
                                  'repository addresses to be shortened; '
                                  'use alias=pullpattern=pushpattern '
                                  'to allow alias:shortname to be used '
                                  'instead of the full URL; the patterns must '
                                  'contain a %s where the shortname gets '
                                  'replaced',
                                  default=defaults['repo-alias'])
        self.settings.string(['bundle-server'],
                             'base URL to download bundles',
                             metavar='URL',
                             default=None)
        self.settings.string(['cache-server'],
                             'HTTP URL of the morph cache server to use',
                             metavar='URL',
                             default=None)
        self.settings.string(['cachedir'],
                             'put build results in DIR',
                             metavar='DIR',
                             default=defaults['cachedir'])
        self.settings.string(['prefix'],
                             'build chunks with prefix PREFIX',
                             metavar='PREFIX', default=defaults['prefix'])
        self.settings.string(['toolchain-target'],
                             'set the TOOLCHAIN_TARGET variable which is used '
                             'in some chunks to determine which architecture '
                             'to build tools for',
                             metavar='TOOLCHAIN_TARGET',
                             default=defaults['toolchain-target'])
        self.settings.string(['target-cflags'],
                             'inject additional CFLAGS into the environment '
                             'that is used to build chunks',
                             metavar='CFLAGS',
                             default='')
        self.settings.string(['tempdir'],
                             'temporary directory to use for builds '
                             '(this is separate from just setting $TMPDIR '
                             'or /tmp because those are used internally '
                             'by things that cannot be on NFS, but '
                             'this setting can point at a directory in '
                             'NFS)',
                             metavar='DIR',
                             default=os.environ.get('TMPDIR'))
        self.settings.boolean(['no-ccache'], 'do not use ccache')
        self.settings.string(['ccache-remotedir'],
                             'allow ccache to download objects from REMOTEDIR '
                             'if they are not cached locally',
                             metavar='REMOTEDIR',
                             default=defaults['ccache-remotedir'])
        self.settings.integer(['ccache-remotenlevels'],
                              'assume ccache directory objects are split into '
                              'NLEVELS levels of subdirectories',
                              metavar='NLEVELS',
                              default=defaults['ccache-remotenlevels'])
        self.settings.boolean(['no-distcc'], 'do not use distcc')
        self.settings.integer(['max-jobs'],
                              'run at most N parallel jobs with make (default '
                              'is to a value based on the number of CPUs '
                              'in the machine running morph',
                              metavar='N',
                              default=defaults['max-jobs'])
        self.settings.boolean(['keep-path'],
                              'do not touch the PATH environment variable')
        self.settings.boolean(['bootstrap'],
                              'build stuff in bootstrap mode; this is '
                              'DANGEROUS and will install stuff on your '
                              'system')
        self.settings.boolean(['ignore-submodules'],
                              'do not cache repositories of git submodules '
                              'or unpack them into the build directory')

        self.settings.boolean(['no-git-update'],
                              'do not update the cached git repositories '
                              'during a build (user must have done that '
                              'already using the update-gits subcommand)')

        self.settings.string_list(['staging-filler'],
                                  'unpack BLOB into staging area for '
                                  'non-bootstrap builds (this will '
                                  'eventually be replaced with proper '
                                  'build dependencies)',
                                  metavar='BLOB')
        self.settings.boolean(['staging-chroot'],
                              'build things in a staging chroot '
                              '(require real root to use)')

    def setup_plugin_manager(self):
        cliapp.Application.setup_plugin_manager(self)

        self.pluginmgr.locations += os.path.join(
            os.path.dirname(morphlib.__file__), 'plugins')

        s = os.environ.get('MORPH_PLUGIN_PATH', '')
        self.pluginmgr.locations += s.split(':')

        self.hookmgr = cliapp.HookManager()
        self.hookmgr.new('new-build-command', cliapp.FilterHook())
        self.system_kind_builder_factory = \
            morphlib.builder2.SystemKindBuilderFactory()

    def itertriplets(self, args):
        '''Generate repo, ref, filename triples from args.'''

        if (len(args) % 3) != 0:
            raise cliapp.AppException('Argument list must have full triplets')

        while args:
            assert len(args) >= 2, args
            yield args[0], args[1], args[2]
            args = args[3:]

    def _itertriplets(self, *args):
        warnings.warn('_itertriplets is deprecated, '
                      'use itertriplets instead', stacklevel=1,
                      category=DeprecationWarning)
        return self.itertriplets(*args)

    def create_source_pool(self, lrc, rrc, triplet):
        pool = morphlib.sourcepool.SourcePool()

        def add_to_pool(reponame, ref, filename, absref, morphology):
            source = morphlib.source.Source(reponame, ref, absref,
                                            morphology, filename)
            pool.add(source)

        self.traverse_morphs([triplet], lrc, rrc,
                             update=not self.settings['no-git-update'],
                             visit=add_to_pool)
        return pool

    def _create_source_pool(self, *args):
        warnings.warn('_create_source_pool is deprecated, '
                      'use create_source_pool instead', stacklevel=1,
                      category=DeprecationWarning)
        return self.create_source_pool(*args)

    def cmd_build(self, args):
        '''Build a binary from a morphology.

        Command line arguments are the repository, git tree-ish reference,
        and morphology filename. Morph takes care of building all dependencies
        before building the morphology. All generated binaries are put into the
        cache.

        (The triplet of command line arguments may be repeated as many
        times as necessary.)

        '''

        build_command = BuildCommand(self)
        build_command = self.hookmgr.call('new-build-command', build_command)
        build_command.build(args)

    def _resolveref(self, lrc, rrc, reponame, ref, update=True):
        '''Resolves the sha1 of the ref in reponame and returns it.

        If update is True then this has the side-effect of updating
        or cloning the repository into the local repo cache.

        '''
        absref = None
        if lrc.has_repo(reponame):
            repo = lrc.get_repo(reponame)
            if update:
                self.status(msg='Updating cached git repository %(reponame)s',
                            reponame=reponame)
                repo.update()
            absref = repo.resolve_ref(ref)
        elif rrc is not None:
            try:
                absref = rrc.resolve_ref(reponame, ref)
            except:
                pass
        if absref is None:
            if update:
                self.status(msg='Caching git repository %(reponame)s',
                            reponame=reponame)
                repo = lrc.cache_repo(reponame)
                repo.update()
            else:
                repo = lrc.get_repo(reponame)
            absref = repo.resolve_ref(ref)
        return absref

    def traverse_morphs(self, triplets, lrc, rrc, update=True,
                        visit=lambda rn, rf, fn, arf, m: None):
        morph_factory = morphlib.morphologyfactory.MorphologyFactory(lrc, rrc)
        queue = collections.deque(triplets)

        while queue:
            reponame, ref, filename = queue.popleft()
            absref = self._resolveref(lrc, rrc, reponame, ref, update)
            morphology = morph_factory.get_morphology(
                reponame, absref, filename)
            visit(reponame, ref, filename, absref, morphology)
            if morphology['kind'] == 'system':
                queue.extend((reponame, ref, '%s.morph' % s)
                             for s in morphology['strata'])
            elif morphology['kind'] == 'stratum':
                if morphology['build-depends']:
                    queue.extend((reponame, ref, '%s.morph' % s)
                                 for s in morphology['build-depends'])
                queue.extend((c['repo'], c['ref'], '%s.morph' % c['morph'])
                             for c in morphology['sources'])

    def _traverse_morphs(self, *args):
        warnings.warn('_traverse_morphs is deprecated, '
                      'use traverse_morphs instead', stacklevel=1,
                      category=DeprecationWarning)
        return self.traverse_morphs(*args)

    def cache_repo_and_submodules(self, cache, url, ref, done):
        subs_to_process = set()
        subs_to_process.add((url, ref))
        while subs_to_process:
            url, ref = subs_to_process.pop()
            done.add((url, ref))
            cached_repo = cache.cache_repo(url)
            cached_repo.update()

            try:
                submodules = morphlib.git.Submodules(self, cached_repo.path,
                                                     ref)
                submodules.load()
            except morphlib.git.NoModulesFileError:
                pass
            else:
                for submod in submodules:
                    if (submod.url, submod.commit) not in done:
                        subs_to_process.add((submod.url, submod.commit))

    def _cache_repo_and_submodules(self, *args):
        warnings.warn('_cache_repo_and_submodules is deprecated, '
                      'use cache_repo_and_submodules instead', stacklevel=1,
                      category=DeprecationWarning)
        return self.cache_repo_and_submodules(*args)

    def _deduce_mine_directory(self):
        dirname = os.getcwd()
        while dirname != '/':
            dot_morph = os.path.join(dirname, '.morph')
            if os.path.isdir(dot_morph):
                return dirname
            dirname = os.path.dirname(dirname)
        return None

    def _resolve_reponame(self, reponame):
        '''Return the full pull URL of a reponame.'''

        resolver = morphlib.repoaliasresolver.RepoAliasResolver(
            self.settings['repo-alias'])
        return resolver.pull_url(reponame)

    def _clone_to_directory(self, dirname, reponame, ref):
        '''Clone a repository below a directory.

        As a side effect, clone it into the morph repository.

        '''

        # Setup.
        if not os.path.exists(self.settings['cachedir']):
            os.mkdir(self.settings['cachedir'])
        cachedir = os.path.join(self.settings['cachedir'], 'gits')
        repo_resolver = morphlib.repoaliasresolver.RepoAliasResolver(
            self.settings['repo-alias'])
        bundle_base_url = self.settings['bundle-server']
        cache = morphlib.localrepocache.LocalRepoCache(
            self, cachedir, repo_resolver, bundle_base_url)

        # Get the repository into the cache; make sure it is up to date.
        repo = cache.cache_repo(reponame)
        if not self.settings['no-git-update']:
            repo.update()

        # Clone it from cache to target directory.
        repo.checkout(ref, os.path.abspath(dirname))

        # Set the origin to point at the original repository.
        morphlib.git.set_remote(self.runcmd, dirname, 'origin', repo.url)

        # Add push url rewrite rule to .git/config.
        self.runcmd(['git', 'config',
                     ('url.%s.pushInsteadOf' %
                      repo_resolver.push_url(reponame)),
                     repo_resolver.pull_url(reponame)], cwd=dirname)

        # Update remotes.
        self.runcmd(['git', 'remote', 'update'], cwd=dirname)

    def _deduce_system_branch(self):
        minedir = self._deduce_mine_directory()
        if minedir is None:
            return None

        if not minedir.endswith('/'):
            minedir += '/'

        cwd = os.getcwd()
        if not cwd.startswith(minedir):
            return None

        return os.path.dirname(cwd[len(minedir):])

    def cmd_edit(self, args):
        '''Edit a component in a system branch.'''

        if len(args) not in (1, 2):
            raise cliapp.AppException('morph edit must get a repository name '
                                      'and commit ref as argument')

        mine_directory = self._deduce_mine_directory()
        system_branch = self._deduce_system_branch()
        if system_branch is None:
            raise morphlib.Error('Cannot deduce system branch')

        morphs_dirname = os.path.join(mine_directory, system_branch, 'morphs')
        if morphs_dirname is None:
            raise morphlib.Error('Can not find morphs directory')

        repo = self._resolve_reponame(args[0])

        if len(args) == 2:
            ref = args[1]
        else:
            ref = self._find_edit_ref(morphs_dirname, repo)
            if ref is None:
                raise morphlib.Error('Cannot deduce commit to start edit from')

        new_repo = os.path.join(mine_directory, system_branch,
                                os.path.basename(repo))
        self._clone_to_directory(new_repo, args[0], ref)

        if system_branch == ref:
            self.runcmd(['git', 'checkout', system_branch],
                        cwd=new_repo)
        else:
            self.runcmd(['git', 'checkout', '-b', system_branch, ref],
                        cwd=new_repo)

        for filename, morph in self._morphs_for_repo(morphs_dirname, repo):
            changed = False
            for spec in morph['sources']:
                spec_repo = self._resolve_reponame(spec['repo'])
                if spec_repo == repo and spec['ref'] != system_branch:
                    if self.settings['verbose']:
                        print ('Replacing ref "%s" with "%s" in %s' %
                               (spec['ref'], system_branch, filename))
                    spec['ref'] = system_branch
                    changed = True
            if changed:
                self._write_morphology(filename, morph)

    def _find_edit_ref(self, morphs_dirname, repo):
        for filename, morph in self._morphs_for_repo(morphs_dirname, repo):
            for spec in morph['sources']:
                spec_repo = self._resolve_reponame(spec['repo'])
                if spec_repo == repo:
                    return spec['ref']
        return None

    def _load_morphologies(self, dirname):
        pattern = os.path.join(dirname, '*.morph')
        for filename in glob.glob(pattern):
            with open(filename) as f:
                text = f.read()
            morphology = morphlib.morph2.Morphology(text)
            yield filename, morphology

    def _morphs_for_repo(self, morphs_dirname, repo):
        for filename, morph in self._load_morphologies(morphs_dirname):
            if morph['kind'] == 'stratum':
                for spec in morph['sources']:
                    spec_repo = self._resolve_reponame(spec['repo'])
                    if spec_repo == repo:
                        yield filename, morph
                        break

    def _write_morphology(self, filename, morphology):
        as_dict = {}
        for key in morphology.keys():
            value = morphology[key]
            if value:
                as_dict[key] = value
        fd, tempname = tempfile.mkstemp(dir=os.path.dirname(filename))
        os.close(fd)
        with open(tempname, 'w') as f:
            json.dump(as_dict, fp=f, indent=4, sort_keys=True)
            f.write('\n')
        os.rename(tempname, filename)

    def status(self, **kwargs):
        '''Show user a status update.

        The keyword arguments are formatted and presented to the user in
        a pleasing manner. Some keywords are special:

        * ``msg`` is the message text; it can use ``%(foo)s`` to embed the
          value of keyword argument ``foo``
        * ``chatty`` should be true when the message is only informative,
          and only useful for users who want to know everything (--verbose)
        * ``error`` should be true when it is an error message

        All other keywords are ignored unless embedded in ``msg``.

        '''

        assert 'msg' in kwargs
        text = kwargs['msg'] % kwargs

        error = kwargs.get('error', False)
        chatty = kwargs.get('chatty', False)
        quiet = self.settings['quiet']
        verbose = self.settings['verbose']

        if error:
            logging.error(text)
        elif chatty:
            logging.debug(text)
        else:
            logging.info(text)

        ok = verbose or error or (not quiet and not chatty)
        if ok:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
            self.output.write('%s %s\n' % (timestamp, text))
            self.output.flush()

    def runcmd(self, argv, *args, **kwargs):
        if 'env' not in kwargs:
            kwargs['env'] = dict(os.environ)

        # convert the command line arguments into a string
        commands = [argv] + list(args)
        for command in commands:
            if isinstance(command, list):
                for i in xrange(0, len(command)):
                    command[i] = str(command[i])
        commands = [' '.join(command) for command in commands]

        # print the command line
        self.status(msg='# %(cmdline)s',
                    cmdline=' | '.join(commands),
                    chatty=True)

        # Log the environment.
        for name in kwargs['env']:
            logging.debug('environment: %s=%s' % (name, kwargs['env'][name]))

        # run the command line
        return cliapp.Application.runcmd(self, argv, *args, **kwargs)
