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
            self.cache_artifacts_locally([artifact])
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
        self.app.status(msg='%(kind)s %(name)s is cached at %(cachepath)s',
                        kind=artifact.source.morphology['kind'],
                        name=artifact.name,
                        cachepath=self.lac.artifact_filename(artifact),
                        chatty=(artifact.source.morphology['kind'] !=
                                "system"))

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
