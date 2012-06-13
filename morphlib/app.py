#!/usr/bin/python
#
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

import morphlib


defaults = {
    'repo-alias': [
        'upstream='
            'git://roadtrain.codethink.co.uk/delta/#'
            'gitano@roadtrain.codethink.co.uk:delta/',
        'baserock='
            'git://roadtrain.codethink.co.uk/baserock/#'
            'gitano@roadtrain.codethink.co.uk:baserock/',
        'gnome='
            'git://git.gnome.org/%s#'
            'ssh://git.gnome.org/git/%s',
        'github='
            'git://github.com/%s#'
            'git@github.com:%s',
    ],
    'cachedir': os.path.expanduser('~/.cache/morph'),
    'max-jobs': morphlib.util.make_concurrency(),
    'prefix': '/usr',
    'toolchain-target': '%s-baserock-linux-gnu' % os.uname()[4],
    'ccache-remotedir': '',
    'ccache-remotenlevels': 2,
}


class Morph(cliapp.Application):

    system_repo_base = 'morphs'
    system_repo_name = 'baserock:%s' % system_repo_base

    def add_settings(self):
        self.settings.boolean(['verbose', 'v'], 'show what is happening')
        self.settings.string_list(['repo-alias'],
                            'define URL prefix aliases to allow repository '
                                'addresses to be shortened; '
                                'use alias=pullpattern=pushpattern '
                                'to allow alias:shortname to be used instead '
                                'of the full URL; the patterns must contain '
                                'a %s where the shortname gets replaced',
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
        s = os.environ.get('MORPH_PLUGIN_PATH', '')
        self.pluginmgr.locations += s.split(':')

    def _itertriplets(self, args):
        '''Generate repo, ref, filename triples from args.'''
        
        if (len(args) % 3) != 0:
            raise cliapp.AppException('Argument list must have full triplets')
        
        while args:
            assert len(args) >= 2, args
            yield args[0], args[1], args[2]
            args = args[3:]

    def _create_source_pool(self, lrc, rrc, triplet):
        pool = morphlib.sourcepool.SourcePool()
        def add_to_pool(reponame, ref, filename, absref, morphology):
            source = morphlib.source.Source(reponame, ref, absref,
                                            morphology, filename)
            pool.add(source)

        self._traverse_morphs([triplet], lrc, rrc,
                              update=not self.settings['no-git-update'],
                              visit=add_to_pool)
        return pool

    def compute_build_order(self, repo_name, ref, filename, ckc, lrc, rrc):
        self.msg('Figuring out the right build order')

        logging.debug('creating source pool')
        srcpool = self._create_source_pool(
                lrc, rrc, (repo_name, ref, filename))

        logging.debug('creating artifact resolver')
        ar = morphlib.artifactresolver.ArtifactResolver()

        logging.debug('resolving artifacts')
        artifacts = ar.resolve_artifacts(srcpool)

        logging.debug('computing cache keys')
        for artifact in artifacts:
            artifact.cache_key = ckc.compute_key(artifact)
            artifact.cache_id = ckc.get_cache_id(artifact)

        logging.debug('computing build order')
        order = morphlib.buildorder.BuildOrder(artifacts)
        
        return order

    def find_what_needs_building(self, order, lac, rac):
        logging.debug('finding what needs to be built')
        needed = []
        for group in order.groups:
            for artifact in group:
                if not lac.has(artifact):
                    if not rac or not rac.has(artifact):
                        needed.append(artifact)
        return needed

    def get_source_repositories(self, needed, lrc):
        logging.debug('cloning/updating cached repos')
        done = set()
        for artifact in needed:
            if self.settings['no-git-update']:
                artifact.source.repo = lrc.get_repo(artifact.source.repo_name)
            else:
                self.msg('Cloning/updating %s' % artifact.source.repo_name)
                artifact.source.repo = lrc.cache_repo(
                        artifact.source.repo_name)
                self._cache_repo_and_submodules(
                        lrc, artifact.source.repo.url,
                        artifact.source.sha1, done)

    def create_staging_area(self):
        if self.settings['bootstrap']:
            staging_root = '/'
            staging_temp = tempfile.mkdtemp(dir=self.settings['tempdir'])
            install_chunks = True
            setup_proc = False
        elif self.settings['staging-chroot']:
            staging_root = tempfile.mkdtemp(dir=self.settings['tempdir'])
            staging_temp = staging_root
            install_chunks = True
            setup_proc = True
        else:
            staging_root = '/'
            staging_temp = tempfile.mkdtemp(dir=self.settings['tempdir'])
            install_chunks = False
            setup_proc = False

        staging_area = morphlib.stagingarea.StagingArea(self,
                                                        staging_root,
                                                        staging_temp)
        if self.settings['staging-chroot']:
            self._install_initial_staging(staging_area)
            
        return staging_area, install_chunks, setup_proc

    def remove_staging_area(self, staging_area):
        if staging_area.dirname != '/':
            staging_area.remove()
        if (staging_area.tempdir != '/' and 
            os.path.exists(staging_area.tempdir)):
            shutil.rmtree(staging_area.tempdir)

    def install_artifacts(self, staging_area, lac, chunk_artifacts):
        for chunk_artifact in chunk_artifacts:
            self.msg('  Installing %s' % chunk_artifact.name)
            handle = lac.get(chunk_artifact)
            staging_area.install_artifact(handle)

    def build_group(self, artifacts, builder, lac, staging_area):
        for artifact in artifacts:
            self.msg('Building %s' % artifact.name)
            builder.build_and_cache(artifact)

    def new_build_env(self):
        return morphlib.buildenvironment.BuildEnvironment(self.settings)

    def new_cache_key_computer(self, build_env):
        return morphlib.cachekeycomputer.CacheKeyComputer(build_env)

    def create_cachedir(self):
        cachedir = self.settings['cachedir']
        if not os.path.exists(cachedir):
            os.mkdir(cachedir)
        return cachedir

    def create_artifact_cachedir(self):
        artifact_cachedir = os.path.join(
                self.settings['cachedir'], 'artifacts')
        if not os.path.exists(artifact_cachedir):
            os.mkdir(artifact_cachedir)
        return artifact_cachedir

    def new_artifact_caches(self):
        cachedir = self.create_cachedir()
        artifact_cachedir = self.create_artifact_cachedir()

        lac = morphlib.localartifactcache.LocalArtifactCache(artifact_cachedir)

        rac_url = self.settings['cache-server']
        if rac_url:
            rac = morphlib.remoteartifactcache.RemoteArtifactCache(rac_url)
        else:
            rac = None
        return lac, rac

    def new_repo_caches(self):
        aliases = self.settings['repo-alias']
        cachedir = self.create_cachedir()
        gits_dir = os.path.join(cachedir, 'gits')
        bundle_base_url = self.settings['bundle-server']
        repo_resolver = morphlib.repoaliasresolver.RepoAliasResolver(aliases)
        lrc = morphlib.localrepocache.LocalRepoCache(self,
                gits_dir, repo_resolver, bundle_base_url=bundle_base_url)

        url = self.settings['cache-server']
        if url:
            rrc = morphlib.remoterepocache.RemoteRepoCache(url, repo_resolver)
        else:
            rrc = None

        return lrc, rrc

    def cmd_build(self, args):
        '''Build a binary from a morphology.
        
        Command line arguments are the repository, git tree-ish reference,
        and morphology filename. Morph takes care of building all dependencies
        before building the morphology. All generated binaries are put into the
        cache.
        
        (The triplet of command line arguments may be repeated as many
        times as necessary.)
        
        '''

        self.msg('Build starts')

        build_env = self.new_build_env()
        ckc = self.new_cache_key_computer(build_env)
        lac, rac = self.new_artifact_caches()
        lrc, rrc = self.new_repo_caches()

        for repo_name, ref, filename in self._itertriplets(args):
            self.msg('Building %s %s %s' % (repo_name, ref, filename))
            order = self.compute_build_order(repo_name, ref, filename,
                                             ckc, lrc, rrc)
            needed = self.find_what_needs_building(order, lac, rac)
            self.get_source_repositories(needed, lrc)
            staging_area, install_chunks, setup_proc = \
                self.create_staging_area()
            builder = morphlib.builder2.Builder(self,
                    staging_area, lac, rac, lrc, build_env,
                    self.settings['max-jobs'], setup_proc)

            to_install = []
            for group in order.groups:
                if install_chunks:
                    self.install_artifacts(staging_area, lac, to_install)
                    del to_install[:]
                for artifact in set(group).difference(set(needed)):
                    self.msg('Using cached %s' % artifact.name)
                wanted = [x for x in group if x in needed]
                self.build_group(wanted, builder, lac, staging_area)
                to_install.extend(
                        x for x in group
                        if x.source.morphology['kind'] == 'chunk')

            # If we are running bootstrap we probably also want the last
            # build group to be installed as well
            if self.settings['bootstrap']:
                self.install_artifacts(staging_area, lac, to_install)

            self.remove_staging_area(staging_area)

    def _install_initial_staging(self, staging_area):
        logging.debug('Pre-populating staging area %s' % staging_area.dirname)
        logging.debug('Fillers: %s' % repr(self.settings['staging-filler']))
        for filename in self.settings['staging-filler']:
            with open(filename, 'rb') as f:
                staging_area.install_artifact(f)

    def cmd_show_dependencies(self, args):
        '''Dumps the dependency tree of all input morphologies.'''

        if not os.path.exists(self.settings['cachedir']):
            os.mkdir(self.settings['cachedir'])
        cachedir = os.path.join(self.settings['cachedir'], 'gits')
        bundle_base_url = self.settings['bundle-server']
        repo_resolver = morphlib.repoaliasresolver.RepoAliasResolver(
                self.settings['repo-alias'])
        lrc = morphlib.localrepocache.LocalRepoCache(self,
                cachedir, repo_resolver, bundle_base_url)
        if self.settings['cache-server']:
            rrc = morphlib.remoterepocache.RemoteRepoCache(
                    self.settings['cache-server'], repo_resolver)
        else:
            rrc = None

        # traverse the morphs to list all the sources
        for repo, ref, filename in self._itertriplets(args):
            pool = self._create_source_pool(lrc, rrc, (repo, ref, filename))

            resolver = morphlib.artifactresolver.ArtifactResolver()
            artifacts = resolver.resolve_artifacts(pool)

            self.output.write('dependency graph for %s|%s|%s:\n' % 
                              (repo, ref, filename))
            for artifact in sorted(artifacts, key=str):
                self.output.write('  %s\n' % artifact)
                for dependency in sorted(artifact.dependencies, key=str):
                    self.output.write('    -> %s\n' % dependency)

            order = morphlib.buildorder.BuildOrder(artifacts)
            self.output.write('build order for %s|%s|%s:\n' %
                              (repo, ref, filename))
            for group in order.groups:
                self.output.write('  group:\n')
                for artifact in group:
                    self.output.write('    %s\n' % artifact)

    def _resolveref(self, lrc, rrc, reponame, ref, update=True):
        '''Resolves the sha1 of the ref in reponame and returns it.

        If update is True then this has the side-effect of updating
        or cloning the repository into the local repo cache.  

        '''
        absref = None
        if lrc.has_repo(reponame):
            repo = lrc.get_repo(reponame)
            if update:
                repo.update()
            absref = repo.resolve_ref(ref)
        elif rrc != None:
            try:
                absref = rrc.resolve_ref(reponame, ref)
            except:
                pass
        if absref == None:
            if update:
                repo = lrc.cache_repo(reponame)
                repo.update()
            else:
                repo = lrc.get_repo(reponame)
            absref = repo.resolve_ref(ref)
        return absref

    def _traverse_morphs(self, triplets, lrc, rrc, update=True,
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

    def cmd_update_gits(self, args):
        '''Update cached git repositories.

        Parse the given morphologies, and their dependencies, and
        update all the git repositories referred to by them in the
        morph cache directory.
        
        '''

        if not os.path.exists(self.settings['cachedir']):
            os.mkdir(self.settings['cachedir'])
        cachedir = os.path.join(self.settings['cachedir'], 'gits')
        repo_resolver = morphlib.repoaliasresolver.RepoAliasResolver(
                self.settings['repo-alias'])
        bundle_base_url = self.settings['bundle-server']
        cache = morphlib.localrepocache.LocalRepoCache(self,
                cachedir, repo_resolver, bundle_base_url)

        subs_to_process = set()
        
        def visit(reponame, ref, filename, absref, morphology):
            self.msg('Updating %s|%s|%s' % (reponame, ref, filename))
            assert cache.has_repo(reponame)
            cached_repo = cache.get_repo(reponame)
            try:
                submodules = morphlib.git.Submodules(self, cached_repo.path,
                                                     absref)
                submodules.load()
            except morphlib.git.NoModulesFileError:
                pass
            else:
                for submod in submodules:
                    subs_to_process.add((submod.url, submod.commit))
            
        self._traverse_morphs(self._itertriplets(args), cache, None,
                              update=True, visit=visit)

        done = set()
        for url, ref in subs_to_process:
            self._cache_repo_and_submodules(cache, url, ref, done)

    def _cache_repo_and_submodules(self, cache, url, ref, done):
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

    def cmd_make_patch(self, args):
        '''Create a Trebuchet patch between two system images.'''
        
        logging.debug('cmd_make_patch starting')
        
        if len(args) != 7:
            raise cliapp.AppException('make-patch requires arguments: '
                                      'name of output file plus two triplest')

        output = args[0]
        repo_name1, ref1, filename1 = args[1:4]
        repo_name2, ref2, filename2 = args[4:7]

        self.settings.require('cachedir')
        cachedir = self.settings['cachedir']
        build_env = morphlib.buildenvironment.BuildEnvironment(self.settings)
        ckc = morphlib.cachekeycomputer.CacheKeyComputer(build_env)
        lac = morphlib.localartifactcache.LocalArtifactCache(
                os.path.join(cachedir, 'artifacts'))
        repo_resolver = morphlib.repoaliasresolver.RepoAliasResolver(
                self.settings['repo-alias'])
        lrc = morphlib.localrepocache.LocalRepoCache(self,
                os.path.join(cachedir, 'gits'), repo_resolver,
                bundle_base_url=self.settings['bundle-server'])
        if self.settings['cache-server']:
            rrc = morphlib.remoterepocache.RemoteRepoCache(
                    self.settings['cache-server'], repo_resolver)
        else:
            rrc = None

        def the_one(source, repo_name, ref, filename):
            return (source.repo_name == repo_name and
                    source.original_ref == ref and
                    source.filename == filename)

        def get_artifact(repo_name, ref, filename):
            srcpool = self._create_source_pool(
                    lrc, rrc, (repo_name, ref, filename))
            ar = morphlib.artifactresolver.ArtifactResolver()
            artifacts = ar.resolve_artifacts(srcpool)
            for artifact in artifacts:
                artifact.cache_key = ckc.compute_key(artifact)
                if the_one(artifact.source, repo_name, ref, filename):
                    return artifact

        artifact1 = get_artifact(repo_name1, ref1, filename1)
        artifact2 = get_artifact(repo_name2, ref2, filename2)

        image_path_1 = lac.get(artifact1).name
        image_path_2 = lac.get(artifact2).name
        
        def setup(path):
            part = morphlib.fsutils.setup_device_mapping(self.runcmd, path)
            mount_point = tempfile.mkdtemp(dir=self.settings['tempdir'])
            morphlib.fsutils.mount(self.runcmd, part, mount_point)
            return mount_point

        def cleanup(path, mount_point):
            try:
                morphlib.fsutils.unmount(self.runcmd, mount_point)
            except:
                pass
            try:
                morphlib.fsutils.undo_device_mapping(self.runcmd, path)
            except:
                pass
            try:
                os.rmdir(mount_point)
            except:
                pass

        try:
            mount_point_1 = setup(image_path_1)
            mount_point_2 = setup(image_path_2)

            self.runcmd(['tbdiff-create', output,
                         os.path.join(mount_point_1, 'factory'),
                         os.path.join(mount_point_2, 'factory')])
        except BaseException:
            raise
        finally:
            cleanup(image_path_1, mount_point_1)
            cleanup(image_path_2, mount_point_2)
        
    def cmd_init(self, args):
        '''Initialize a mine.'''
        
        if not args:
            args = ['.']
        elif len(args) > 1:
            raise cliapp.AppException('init must get at most one argument')

        dirname = args[0]

        if os.path.exists(dirname):
            if os.listdir(dirname) != []:
                raise cliapp.AppException('can only initialize empty '
                                          'directory: %s' % dirname)
        else:
            raise cliapp.AppException('can only initialize an existing '
                                        'empty directory: %s' % dirname)

        os.mkdir(os.path.join(dirname, '.morph'))

    def _deduce_mine_directory(self):
        dirname = os.getcwd()
        while dirname != '/':
            dot_morph = os.path.join(dirname, '.morph')
            if os.path.isdir(dot_morph):
                return dirname
            dirname = os.path.dirname(dirname)
        return None

    def cmd_minedir(self, args):
        '''Find morph mine directory from current working directory.'''
        
        dirname = self._deduce_mine_directory()
        if dirname is None:
            raise cliapp.AppException("Can't find the mine directory")
        self.output.write('%s\n' % dirname)
    
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
        cache = morphlib.localrepocache.LocalRepoCache(self,
                cachedir, repo_resolver, bundle_base_url)

        # Get the repository into the cache; make sure it is up to date.
        repo = cache.cache_repo(reponame)
        if not self.settings['no-git-update']:
            repo.update()
        
        # Clone it from cache to target directory.
        repo.checkout(ref, os.path.abspath(dirname))
        
        # Set the origin to point at the original repository.
        morphlib.git.set_remote(self.runcmd, dirname, 'origin', repo.url)
        
        # Add push url rewrite rule to .git/config.
        filename = os.path.join(dirname, '.git', 'config')
        with open(filename, 'a') as f:
            f.write('\n')
            f.write('[url "%s"]\n' % repo_resolver.push_url(reponame))
            f.write('\tpushInsteadOf = %s\n' %repo_resolver.pull_url(reponame))
        
        # Update remotes.
        self.runcmd(['git', 'remote', 'update'], cwd=dirname)

    def cmd_branch(self, args):
        '''Branch the whole system.'''
        
        if len(args) not in [1, 2]:
            raise cliapp.AppException('morph branch needs name of branch '
                                        'as parameter')

        new_branch = args[0]
        commit = 'master' if len(args) == 1 else args[1]

        # Create the system branch directory.
        os.makedirs(new_branch)

        # Clone into system branch directory.
        new_repo = os.path.join(new_branch, self.system_repo_base)
        self._clone_to_directory(new_repo, self.system_repo_name, commit)
        
        # Create a new branch in the local morphs repository.
        self.runcmd(['git', 'checkout', '-b', new_branch, commit],
                    cwd=new_repo)

    def cmd_checkout(self, args):
        '''Check out an existing system branch.'''

        if len(args) != 1:
            raise cliapp.AppException('morph checkout needs name of '
                                        'branch as parameter')

        system_branch = args[0]

        # Create the system branch directory.
        os.makedirs(system_branch)

        # Clone into system branch directory.
        new_repo = os.path.join(system_branch, self.system_repo_base)
        self._clone_to_directory(
            new_repo, self.system_repo_name, system_branch)

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
    
    def cmd_show_system_branch(self, args):
        '''Print name of current system branch.
        
        This must be run in the system branch's ``morphs`` repository.
        
        '''
        
        system_branch = self._deduce_system_branch()
        if system_branch is None:
            raise cliapp.AppException("Can't determine system branch")
        self.output.write('%s\n' % system_branch)
    
    def cmd_edit(self, args):
        '''Edit a component in a system branch.'''
        
        if len(args) not in (1,2):
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

    def cmd_merge(self, args):
        '''Merge specified repositories from another system branch.'''
        
        if len(args) == 0:
            raise cliapp.AppException('morph merge must get a branch name '
                                        'and some repo names as arguments')

        other_branch = args[0]
        mine = self._deduce_mine_directory()
        this_branch = self._deduce_system_branch()
        
        for repo in args[1:]:
            repo = self._resolve_reponame(repo)
            basename = os.path.basename(repo)
            pull_from = os.path.join(mine, other_branch, basename)
            repo_dir = os.path.join(mine, this_branch, basename)
            self.runcmd(['git', 'pull', pull_from, other_branch], cwd=repo_dir)

    def cmd_petrify(self, args):
        '''Make refs to chunks be absolute SHA-1s.'''

        if not os.path.exists(self.settings['cachedir']):
            os.mkdir(self.settings['cachedir'])
        cachedir = os.path.join(self.settings['cachedir'], 'gits')
        repo_resolver = morphlib.repoaliasresolver.RepoAliasResolver(
                self.settings['repo-alias'])
        bundle_base_url = self.settings['bundle-server']
        cache = morphlib.localrepocache.LocalRepoCache(self,
                cachedir, repo_resolver, bundle_base_url)
        
        for filename in args:
            with open(filename) as f:
                morph = json.load(f)
            
            if morph['kind'] != 'stratum':
                self.msg('Not a stratum: %s' % filename)
                continue

            self.msg('Petrifying %s' % filename)

            for source in morph['sources']:
                reponame = source.get('repo', source['name'])
                ref = source['ref']
                self.msg('.. looking up sha1 for %s %s' % (reponame, ref))
                repo = cache.get_repo(reponame)
                source['ref'] = repo.resolve_ref(ref)
            
            with open(filename, 'w') as f:
                json.dump(morph, f, indent=2)

    def msg(self, msg):
        '''Show a message to the user about what is going on.'''
        logging.debug(msg)
        if self.settings['verbose']:
            self.output.write('%s\n' % msg)
            self.output.flush()

    def runcmd(self, argv, *args, **kwargs):
        # check which msg function to use
        msg = self.msg
        if 'msg' in kwargs:
            msg = kwargs['msg']
            del kwargs['msg']

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
        msg('# %s' % ' | '.join(commands))
        
        # Log the environment.
        for name in kwargs['env']:
            logging.debug('environment: %s=%s' % (name, kwargs['env'][name]))

        # run the command line
        return cliapp.Application.runcmd(self, argv, *args, **kwargs)

