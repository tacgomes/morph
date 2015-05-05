# distbuild/artifact_reference.py -- Decode/encode ArtifactReference objects
#
# Copyright (C) 2012, 2014-2015  Codethink Limited
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


import json
import logging
import yaml

import morphlib


class ArtifactReference(object): # pragma: no cover

    '''Container for some basic information about an artifact.'''

    def __init__(self, basename, encoded):
        self._basename = basename
        self._dict = encoded

    def __getattr__(self, name):
        if not name.startswith('_'):
            return self._dict[name]
        else:
            super(ArtifactReference, self).__getattr__(name)

    def __setattr__(self, name, val):
        if not name.startswith('_'):
            self._dict[name] = val
        else:
            super(ArtifactReference, self).__setattr__(name, val)

    def basename(self):
        return self._basename

    def walk(self):
        done = set()

        def depth_first(a):
            if a not in done:
                done.add(a)
                for dep in a.dependencies:
                    for ret in depth_first(dep):
                        yield ret
                yield a

        return list(depth_first(self))


def encode_artifact(artifact, repo, ref):
    '''Encode part of an Artifact object and dependencies into string form.'''

    def get_source_dict(source):
        source_dict = {
            'filename': source.filename,
            'kind': source.morphology['kind'],
            'source_name': source.name,
            'source_repo': source.repo_name,
            'source_ref': source.original_ref,
            'source_sha1': source.sha1,
            'source_artifact_names': [],
            'dependencies': []
        }
        for dependency in source.dependencies:
            source_dict['dependencies'].append(dependency.basename())
        for source_artifact_name in source.artifacts:
            source_dict['source_artifact_names'].append(source_artifact_name)
        return source_dict

    def get_artifact_dict(a):
        if artifact.source.morphology['kind'] == 'system': # pragma: no cover
            arch = artifact.source.morphology['arch']
        else:
            arch = artifact.arch

        a_dict = {
            'arch': arch,
            'cache_key': a.source.cache_key,
            'name': a.name,
            'repo': repo,
            'ref': ref,
        }
        return a_dict

    encoded_artifacts = {}
    encoded_sources = {}

    root_filename = artifact.source.filename
    for a in artifact.walk():
        if a.basename() not in encoded_artifacts: # pragma: no cover
            encoded_artifacts[a.basename()] = get_artifact_dict(a)
            encoded_sources[a.source.cache_key] = get_source_dict(a.source)

    content = {
        'root-artifact': artifact.basename(),
        'root-filename': root_filename,
        'artifacts': encoded_artifacts,
        'sources': encoded_sources
    }

    return json.dumps(yaml.dump(content))


def encode_artifact_reference(artifact): # pragma: no cover
    '''Encode an ArtifactReference object into string form.

    The ArtifactReference object is encoded such that it can be recreated by
    ``decode_artifact_reference``.

    '''
    artifact_dict = {
        'arch': artifact.arch,
        'cache_key': artifact.cache_key,
        'name': artifact.name,
        'repo': artifact.repo,
        'ref': artifact.ref
    }
    source_dict = {
        'filename': artifact.filename,
        'kind': artifact.kind,
        'source_name': artifact.source_name,
        'source_repo': artifact.source_repo,
        'source_ref': artifact.source_ref,
        'source_sha1': artifact.source_sha1,
        'source_artifact_names': [],
        'dependencies': []
    }

    for dependency in artifact.dependencies:
        source_dict['dependencies'].append(dependency.basename())

    for source_artifact_name in artifact.source_artifact_names:
        source_dict['source_artifact_names'].append(source_artifact_name)

    content = {
        'root-artifact': artifact.basename(),
        'root-filename': artifact.root_filename,
        'artifacts': {artifact.basename(): artifact_dict},
        'sources': {artifact.cache_key: source_dict}
    }

    return json.dumps(yaml.dump(content))


def decode_artifact_reference(encoded):
    '''Decode an ArtifactReference object from `encoded`.

    The argument should be a string returned by ``encode_artifact``
    or ``encode_artifact_reference``. The decoded ArtifactReference
    object will be sufficient to represent a build graph and contain
    enough information to allow `morph worker-build` to calculate a
    build graph and find the original Artifact object it needs to
    build.

    '''
    content = yaml.load(json.loads(encoded))
    root = content['root-artifact']
    encoded_artifacts = content['artifacts']
    encoded_sources = content['sources']

    artifacts = {}

    # decode artifacts
    for basename, artifact_dict in encoded_artifacts.iteritems():
        artifact_dict.update(encoded_sources[artifact_dict['cache_key']])
        artifact = ArtifactReference(basename, artifact_dict)
        artifact.root_filename = content['root-filename']
        artifacts[basename] = artifact

    # add dependencies
    for basename, a_dict in encoded_artifacts.iteritems():
        artifact = artifacts[basename]
        artifact.dependencies = [artifacts.get(dep)
                                 for dep in artifact.dependencies]

    return artifacts[root]
