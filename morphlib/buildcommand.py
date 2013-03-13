# Copyright (C) 2011-2013  Codethink Limited
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


import os
import shutil
import logging
import tempfile

import morphlib


class BuildCommand(object):

    '''High level logic for building.

    This controls how the whole build process goes. This is a separate
    class to enable easy experimentation of different approaches to
    the various parts of the process.

    '''

    def __init__(self, app):
        self.supports_local_build = True

        self.app = app
        self.lac, self.rac = self.new_artifact_caches()
        self.lrc, self.rrc = self.new_repo_caches()

    def build(self, args):
        '''Build triplets specified on command line.'''

        self.app.status(msg='Build starts', chatty=True)

        for repo_name, ref, filename in self.app.itertriplets(args):
            self.app.status(msg='Building %(repo_name)s %(ref)s %(filename)s',
                            repo_name=repo_name, ref=ref, filename=filename)
            artifact = self.get_artifact_object(repo_name, ref, filename)
            self.build_in_order(artifact)

        self.app.status(msg='Build ends successfully')

    def new_artifact_caches(self):
        '''Create interfaces for the build artifact caches.

        This includes creating the directories on disk if they are missing.

        '''
        return morphlib.util.new_artifact_caches(self.app.settings)

    def new_repo_caches(self):
        return morphlib.util.new_repo_caches(self.app)

    def new_build_env(self, arch):
        '''Create a new BuildEnvironment instance.'''
        return morphlib.buildenvironment.BuildEnvironment(self.app.settings,
                                                          arch)

    def get_artifact_object(self, repo_name, ref, filename):
        '''Create an Artifact object representing the given triplet.'''
        
        self.app.status(msg='Figuring out the right build order')

        self.app.status(msg='Creating source pool', chatty=True)
        srcpool = self.app.create_source_pool(
            self.lrc, self.rrc, (repo_name, ref, filename))

        self.app.status(
            msg='Validating cross-morphology references', chatty=True)
        self._validate_cross_morphology_references(srcpool)

        self.app.status(msg='Creating artifact resolver', chatty=True)
        ar = morphlib.artifactresolver.ArtifactResolver()

        self.app.status(msg='Resolving artifacts', chatty=True)
        artifacts = ar.resolve_artifacts(srcpool)

        self.app.status(msg='Computing build order', chatty=True)
        root_artifact = self._find_root_artifact(artifacts)

        root_kind = root_artifact.source.morphology['kind']
        if root_kind != 'system':
            raise morphlib.Error(
                'Building a %s directly is not supported' % root_kind)
        arch = root_artifact.source.morphology['arch']

        self.app.status(msg='Creating build environment for %(arch)s',
                        arch=arch, chatty=True)
        build_env = self.new_build_env(arch)

        self.app.status(msg='Computing cache keys', chatty=True)
        ckc = morphlib.cachekeycomputer.CacheKeyComputer(build_env)
        for artifact in artifacts:
            artifact.cache_key = ckc.compute_key(artifact)
            artifact.cache_id = ckc.get_cache_id(artifact)

        root_artifact.build_env = build_env
        return root_artifact

    def _validate_cross_morphology_references(self, srcpool):
        '''Perform validation across all morphologies involved in the build'''

        stratum_names = []

        for src in srcpool:
            kind = src.morphology['kind']

            # Verify that chunks pointed to by strata really are chunks, etc.
            method_name = '_validate_cross_refs_for_%s' % kind
            if hasattr(self, method_name):
                logging.debug('Calling %s' % method_name)
                getattr(self, method_name)(src, srcpool)
            else:
                logging.warning('No %s' % method_name)

            # Verify stratum build-depends agree with the system's contents.
            # It's not an error to build-depend on a stratum that isn't
            # included in the target system, but if it is included, the repo
            # and ref fields must match.
            if src.morphology['kind'] == 'stratum':
                name = src.morphology['name']
                if name in stratum_names:
                    raise morphlib.Error(
                        "Conflicting versions of stratum '%s' appear in the "
                        "build. Check the contents of the system against the "
                        "build-depends of the strata." % name)
                stratum_names.append(name)

    def _validate_cross_refs_for_system(self, src, srcpool):
        self._validate_cross_refs_for_xxx(
            src, srcpool, src.morphology['strata'], 'stratum')

    def _validate_cross_refs_for_stratum(self, src, srcpool):
        self._validate_cross_refs_for_xxx(
            src, srcpool, src.morphology['chunks'], 'chunk')

    def _validate_cross_refs_for_xxx(self, src, srcpool, specs, wanted):
        for spec in specs:
            repo_name = spec['repo']
            ref = spec['ref']
            filename = '%s.morph' % spec['morph']
            logging.debug(
                'Validating cross ref to %s:%s:%s' %
                    (repo_name, ref, filename))
            other = srcpool.lookup(repo_name, ref, filename)
            if other.morphology['kind'] != wanted:
                raise morphlib.Error(
                    '%s %s references %s:%s:%s which is a %s, '
                        'instead of a %s' %
                        (src.morphology['kind'],
                         src.morphology['name'],
                         repo_name,
                         ref,
                         filename,
                         other.morphology['kind'],
                         wanted))

    def _find_root_artifact(self, artifacts):
        '''Find the root artifact among a set of artifacts in a DAG.
        
        It would be nice if the ArtifactResolver would return its results in a
        more useful order to save us from needing to do this -- the root object
        is known already since that's the one the user asked us to build.
        
        '''

        maybe = set(artifacts)
        for a in artifacts:
            for dep in a.dependencies:
                if dep in maybe:
                    maybe.remove(dep)
        assert len(maybe) == 1
        return maybe.pop()

    def build_in_order(self, root_artifact):
        '''Build everything specified in a build order.'''

        self.app.status(msg='Building a set of artifacts', chatty=True)
        build_env = root_artifact.build_env
        artifacts = root_artifact.walk()
        old_prefix = self.app.status_prefix
        for i, a in enumerate(artifacts):
            self.app.status_prefix = (
                old_prefix + '[Build %d/%d] ' % ((i+1), len(artifacts)))

            self.app.status(msg='Checking if %(kind)s %(name)s needs building',
                            kind=a.source.morphology['kind'], name=a.name)

            if self.is_built(a):
                self.app.status(msg='The %(kind)s %(name)s is already built',
                                kind=a.source.morphology['kind'], name=a.name)
                self.cache_artifacts_locally([a])
            else:
                self.app.status(msg='Building %(kind)s %(name)s',
                                kind=a.source.morphology['kind'], name=a.name)
                self.build_artifact(a, build_env)

            self.app.status(msg='%(kind)s %(name)s is cached at %(cachepath)s',
                            kind=a.source.morphology['kind'], name=a.name,
                            cachepath=self.lac.artifact_filename(a),
                            chatty=(a.source.morphology['kind'] != "system"))
        self.app.status_prefix = old_prefix

    def is_built(self, artifact):
        '''Does either cache already have the artifact?'''
        return self.lac.has(artifact) or (self.rac and self.rac.has(artifact))

    def build_artifact(self, artifact, build_env):
        '''Build one artifact.

        All the dependencies are assumed to be built and available
        in either the local or remote cache already.

        '''
        self.get_sources(artifact)
        deps = self.get_recursive_deps(artifact)
        self.cache_artifacts_locally(deps)

        setup_mounts = False
        if artifact.source.morphology['kind'] == 'chunk':
            build_mode = artifact.source.build_mode
            extra_env = {'PREFIX': artifact.source.prefix}

            dep_prefix_set = artifact.get_dependency_prefix_set()
            extra_path = [os.path.join(d, 'bin') for d in dep_prefix_set]

            if build_mode not in ['bootstrap', 'staging', 'test']:
                logging.warning('Unknown build mode %s for chunk %s. '
                                'Defaulting to staging mode.' %
                                (build_mode, artifact.name))
                build_mode = 'staging'

            use_chroot = build_mode=='staging'
            staging_area = self.create_staging_area(build_env,
                                                    use_chroot,
                                                    extra_env=extra_env,
                                                    extra_path=extra_path)
            self.install_fillers(staging_area)
            self.install_dependencies(staging_area, deps, artifact)
        else:
            staging_area = self.create_staging_area(build_env, False)

        self.build_and_cache(staging_area, artifact, setup_mounts)
        self.remove_staging_area(staging_area)

    def get_recursive_deps(self, artifact):
        return artifact.walk()[:-1]

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
                rac_file = self.rac.get(artifact)
                lac_file = self.lac.put(artifact)
                copy(rac_file, lac_file)

            if artifact.source.morphology.needs_artifact_metadata_cached:
                if not self.lac.has_artifact_metadata(artifact, 'meta'):
                    self.app.status(msg='Fetching to local cache: '
                                        'artifact metadata %(name)s',
                                    name=artifact.name)
                    copy(self.rac.get_artifact_metadata(artifact, 'meta'),
                         self.lac.put_artifact_metadata(artifact, 'meta'))

    def create_staging_area(self, build_env, use_chroot=True, extra_env={},
                            extra_path=[]):
        '''Create the staging area for building a single artifact.'''

        self.app.status(msg='Creating staging area')
        staging_dir = tempfile.mkdtemp(dir=self.app.settings['tempdir'])
        staging_area = morphlib.stagingarea.StagingArea(
            self.app, staging_dir, build_env, use_chroot, extra_env,
            extra_path)
        return staging_area

    def remove_staging_area(self, staging_area):
        '''Remove the staging area.'''

        self.app.status(msg='Removing staging area')
        staging_area.remove()

    def install_fillers(self, staging_area):
        '''Install staging fillers into the staging area.'''

        logging.debug('Pre-populating staging area %s' % staging_area.dirname)
        logging.debug('Fillers: %s' %
                      repr(self.app.settings['staging-filler']))
        for filename in self.app.settings['staging-filler']:
            with open(filename, 'rb') as f:
                self.app.status(msg='Installing %(filename)s',
                                filename=filename)
                staging_area.install_artifact(f)

    # Nasty hack to avoid installing chunks built in 'bootstrap' mode in a
    # different stratum when constructing staging areas.
    def is_stratum(self, a):
        return a.source.morphology['kind'] == 'stratum'

    def in_same_stratum(self, a, b):
        return len(filter(self.is_stratum, a.dependencies)) == \
               len(filter(self.is_stratum, b.dependencies))

    def install_dependencies(self, staging_area, artifacts, target_artifact):
        '''Install chunk artifacts into staging area.

        We only ever care about chunk artifacts as build dependencies,
        so this is not a generic artifact installer into staging area.
        Any non-chunk artifacts are silently ignored.

        All artifacts MUST be in the local artifact cache already.

        '''

        for artifact in artifacts:
            if artifact.source.morphology['kind'] != 'chunk':
                continue
            if artifact.source.build_mode == 'bootstrap':
               if not self.in_same_stratum(artifact, target_artifact):
                    continue
            self.app.status(msg='[%(name)s] Installing chunk %(chunk_name)s',
                            name=target_artifact.name,
                            chunk_name=artifact.name)
            handle = self.lac.get(artifact)
            staging_area.install_artifact(handle)

        if target_artifact.source.build_mode == 'staging':
            morphlib.builder2.ldconfig(self.app.runcmd, staging_area.dirname)

    def build_and_cache(self, staging_area, artifact, setup_mounts):
        '''Build an artifact and put it into the local artifact cache.'''

        self.app.status(msg='Starting actual build: %(name)s',
                        name=artifact.name)
        setup_mounts = self.app.settings['staging-chroot']
        builder = morphlib.builder2.Builder(
            self.app, staging_area, self.lac, self.rac, self.lrc,
            self.app.settings['max-jobs'], setup_mounts)
        return builder.build_and_cache(artifact)
