# Copyright (C) 2013-2015  Codethink Limited
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
#
# =*= License: GPL-2 =*=

import collections
import yaml

import morphlib


class MorphologySyntaxError(morphlib.Error):
    pass


class MorphologyNotYamlError(MorphologySyntaxError):

    def __init__(self, morphology, errmsg):
        self.msg = 'Syntax error in morphology %s:\n%s' % (morphology, errmsg)


class NotADictionaryError(MorphologySyntaxError):

    def __init__(self, morph_filename):
        self.msg = 'Not a dictionary: morphology %s' % morph_filename


class MorphologyValidationError(morphlib.Error):
    pass


class UnknownKindError(MorphologyValidationError):

    def __init__(self, kind, morph_filename):
        self.msg = (
            'Unknown kind %s in morphology %s' % (kind, morph_filename))


class MissingFieldError(MorphologyValidationError):

    def __init__(self, field, morphology_name):
        self.field = field
        self.morphology_name = morphology_name
        self.msg = (
            'Missing field %s from morphology %s' % (field, morphology_name))


class UnknownArchitectureError(MorphologyValidationError):

    def __init__(self, arch, morph_filename):
        self.msg = ('Unknown architecture %s in morphology %s'
                    % (arch, morph_filename))


class UnknownBuildSystemError(MorphologyValidationError):

    def __init__(self, build_system, morph_filename):
        self.msg = ('Undefined build system %s in morphology %s'
                    % (build_system, morph_filename))


class NoStratumBuildDependenciesError(MorphologyValidationError):

    def __init__(self, stratum_name, morph_filename):
        self.msg = (
            'Stratum %s has no build dependencies in %s' %
                (stratum_name, morph_filename))


class DuplicateChunkError(MorphologyValidationError):

    def __init__(self, stratum_name, chunk_name):
        self.stratum_name = stratum_name
        self.chunk_name = chunk_name
        MorphologyValidationError.__init__(
            self, 'Duplicate chunk %(chunk_name)s '\
                  'in stratum %(stratum_name)s' % locals())


class ChunkSpecConflictingFieldsError(MorphologyValidationError):

    def __init__(self, fields, chunk_name, stratum_name):
        self.chunk_name = chunk_name
        self.stratum_name = stratum_name
        self.fields = fields
        MorphologyValidationError.__init__(
            self, 'Conflicting fields "%s" for %s in stratum %s.' % (
                ', and '.join(fields), chunk_name, stratum_name))


class ChunkSpecNoBuildInstructionsError(MorphologyValidationError):

    def __init__(self, chunk_name, stratum_name):
        self.chunk_name = chunk_name
        self.stratum_name = stratum_name
        self.msg = (
            'Chunk %(chunk_name)s in stratum %(stratum_name)s has no '
            'build-system defined, and no chunk .morph file referenced '
            'either. Please specify how to build the chunk, either by setting '
            '"build-system: " in the stratum, or adding a chunk .morph file '
            'and setting "morph: " in the stratum.' % locals())


class DuplicateStratumError(MorphologyValidationError):

    def __init__(self, system_name, stratum_name):
        self.system_name = system_name
        self.stratum_name = stratum_name
        MorphologyValidationError.__init__(
            self, 'Duplicate stratum %(stratum_name)s '\
                  'in system %(system_name)s' % locals())


class DependsOnSelfError(MorphologyValidationError):

    def __init__(self, name, filename):
        msg = ("Stratum %(name)s build-depends on itself (%(filename)s)"
               % locals())
        MorphologyValidationError.__init__(self, msg)


class DuplicateDeploymentNameError(MorphologyValidationError):

    def __init__(self, cluster_filename, duplicates):
        self.duplicates = duplicates
        self.cluster_filename = cluster_filename
        morphlib.Error.__init__(self,
            'Cluster %s contains the following duplicate deployment names:%s'
            % (cluster_filename, '\n    ' + '\n    '.join(duplicates)))


class MorphologyDumper(yaml.SafeDumper):
    keyorder = (
        'name',
        'kind',
        'description',
        'arch',
        'strata',
        'configuration-extensions',
        'morph',
        'repo',
        'ref',
        'unpetrify-ref',
        'build-depends',
        'build-mode',
        'artifacts',
        'max-jobs',
        'products',
        'chunks',
        'build-system',
        'pre-configure-commands',
        'configure-commands',
        'post-configure-commands',
        'pre-build-commands',
        'build-commands',
        'pre-test-commands',
        'test-commands',
        'post-test-commands',
        'post-build-commands',
        'pre-install-commands',
        'install-commands',
        'post-install-commands',
        'artifact',
        'include',
        'systems',
        'deploy-defaults',
        'deploy',
        'type',
        'location',
    )

    @classmethod
    def _iter_in_global_order(cls, mapping):
        for key in cls.keyorder:
            if key in mapping:
                yield key, mapping[key]
        for key in sorted(mapping.iterkeys()):
            if key not in cls.keyorder:
                yield key, mapping[key]

    @classmethod
    def _represent_dict(cls, dumper, mapping):
        return dumper.represent_mapping('tag:yaml.org,2002:map',
                                        cls._iter_in_global_order(mapping))

    @classmethod
    def _represent_str(cls, dumper, orig_data):
        fallback_representer = yaml.representer.SafeRepresenter.represent_str
        try:
            data = unicode(orig_data, 'ascii')
            if data.count('\n') == 0:
                return fallback_representer(dumper, orig_data)
        except UnicodeDecodeError:
            try:
                data = unicode(orig_data, 'utf-8')
                if data.count('\n') == 0:
                    return fallback_representer(dumper, orig_data)
            except UnicodeDecodeError:
                return fallback_representer(dumper, orig_data)
        return dumper.represent_scalar(u'tag:yaml.org,2002:str',
                                       data, style='|')

    @classmethod
    def _represent_unicode(cls, dumper, data):
        if data.count('\n') == 0:
            return yaml.representer.SafeRepresenter.represent_unicode(dumper,
                                                                      data)
        return dumper.represent_scalar(u'tag:yaml.org,2002:str',
                                       data, style='|')

    def __init__(self, *args, **kwargs):
        yaml.SafeDumper.__init__(self, *args, **kwargs)
        self.add_representer(dict, self._represent_dict)
        self.add_representer(str, self._represent_str)
        self.add_representer(unicode, self._represent_unicode)


class MorphologyLoader(object):

    '''Load morphologies from disk, or save them back to disk.'''

    _static_defaults = {
        'chunk': {
            'description': '',
            'pre-configure-commands': None,
            'configure-commands': None,
            'post-configure-commands': None,
            'pre-build-commands': None,
            'build-commands': None,
            'post-build-commands': None,
            'pre-test-commands': None,
            'test-commands': None,
            'post-test-commands': None,
            'pre-install-commands': None,
            'install-commands': None,
            'post-install-commands': None,
            'pre-strip-commands': None,
            'strip-commands': None,
            'post-strip-commands': None,
            'devices': [],
            'products': [],
            'max-jobs': None,
            'build-system': 'manual',
            'build-mode': 'staging',
            'prefix': '/usr',
            'system-integration': [],
        },
        'stratum': {
            'chunks': [],
            'description': '',
            'build-depends': [],
            'products': [],
        },
        'system': {
            'description': '',
            'arch': None,
            'configuration-extensions': [],
        },
        'cluster': {
            'description': '',
        },
    }

    def __init__(self, predefined_build_systems={}, schemas={}):
        self._predefined_build_systems = predefined_build_systems.copy()
        self._schemas = schemas

        if 'manual' not in self._predefined_build_systems:
            self._predefined_build_systems['manual'] = \
                morphlib.buildsystem.ManualBuildSystem()

    def load_from_string(self, string, filename='string',
                         set_defaults=True):  # pragma: no cover
        '''Load a morphology from a string.

        Return the Morphology object.

        '''

        try:
            obj = yaml.safe_load(string)
        except yaml.error.YAMLError as e:
            raise MorphologyNotYamlError(filename, e)

        if not isinstance(obj, dict):
            raise NotADictionaryError(filename)

        m = morphlib.morphology.Morphology(obj)
        m.filename = filename
        self.validate(m)

        if set_defaults:
            self.set_commands(m)
            self.set_defaults(m)
        return m

    def load_from_file(self, filename, set_defaults=True):
        '''Load a morphology from a named file.

        Return the Morphology object.

        '''

        with open(filename) as f:
            text = f.read()
        return self.load_from_string(text, filename=filename)

    def save_to_string(self, morphology):
        '''Return normalised textual form of morphology.'''

        return yaml.dump(morphology.data, Dumper=MorphologyDumper,
                         default_flow_style=False)

    def save_to_file(self, filename, morphology):
        '''Save a morphology object to a named file.'''

        text = self.save_to_string(morphology)
        with morphlib.savefile.SaveFile(filename, 'w') as f:
            f.write(text)

    def validate(self, morph):
        '''Validate a morphology.'''

        # Validate that the kind field is there.
        if 'kind' not in morph:
            raise MissingFieldError('kind', morph.filename)

        # The rest of the validation is dependent on the kind.
        kind = morph['kind']
        if kind not in ('system', 'stratum', 'chunk', 'cluster'):
            raise UnknownKindError(morph['kind'], morph.filename)

        error = morphlib.util.validate_json(
                dict(morph), self._schemas[kind], morph.filename)
        if error:
            raise MorphologyValidationError(error)

        getattr(self, '_validate_%s' % kind)(morph)

    @classmethod
    def get_subsystem_names(cls, system): # pragma: no cover
        for subsystem in system.get('subsystems', []):
            for name in subsystem['deploy'].iterkeys():
                yield name
            for name in cls.get_subsystem_names(subsystem):
                yield name

    def _validate_cluster(self, morph):

        # Deployment names must be unique within a cluster
        deployments = collections.Counter()
        for system in morph['systems']:
            deployments.update(system['deploy'].iterkeys())
            if 'subsystems' in system:
                deployments.update(self.get_subsystem_names(system))
        duplicates = set(deployment for deployment, count
                         in deployments.iteritems() if count > 1)
        if duplicates:
            raise DuplicateDeploymentNameError(morph.filename, duplicates)

    def _validate_system(self, morph):
        # Architecture name must be known.
        if morph['arch'] not in morphlib.valid_archs:
            raise UnknownArchitectureError(morph['arch'], morph.filename)

        # All stratum names should be unique within a system.
        names = set()
        strata = morph['strata']
        for spec in strata:
            name = spec['morph']
            if name in names:
                raise DuplicateStratumError(morph['name'], name)
            names.add(name)

    def _validate_stratum(self, morph):
        # Require build-dependencies for the stratum itself, unless
        # it has chunks built in bootstrap mode.
        if 'build-depends' in morph:
            for dep in morph['build-depends']:
                if dep['morph'] == morph.filename:
                    raise DependsOnSelfError(morph['name'], morph.filename)
        else:
            for spec in morph['chunks']:
                if spec.get('build-mode') in ['bootstrap', 'test']:
                    break
            else:
                raise NoStratumBuildDependenciesError(
                    morph['name'], morph.filename)

        # All chunk names must be unique within a stratum.
        names = set()
        for spec in morph['chunks']:
            name = spec['name']
            if name in names:
                raise DuplicateChunkError(morph['name'], name)
            names.add(name)

        # Check each reference to a chunk.
        for spec in morph['chunks']:
            chunk_name = spec['name']
            # Either 'morph' or 'build-system' must be specified.
            if 'morph' in spec and 'build-system' in spec:
                raise ChunkSpecConflictingFieldsError(
                    ['morph', 'build-system'], chunk_name, morph.filename)
            if 'morph' not in spec and 'build-system' not in spec:
                raise ChunkSpecNoBuildInstructionsError(
                    chunk_name, morph.filename)

    def _validate_chunk(self, morph):
        pass

    def set_defaults(self, morphology):
        '''Set all missing fields in the morpholoy to their defaults.

        The morphology is assumed to be valid.

        '''

        kind = morphology['kind']
        defaults = self._static_defaults[kind]
        for key in defaults:
            if key not in morphology:
                morphology[key] = defaults[key]

        getattr(self, '_set_%s_defaults' % kind)(morphology)

    def _set_cluster_defaults(self, morph):
        for system in morph.get('systems', []):
            if 'deploy-defaults' not in system:
                system['deploy-defaults'] = {}
            if 'deploy' not in system:
                system['deploy'] = {}

    def _set_system_defaults(self, morph):
        pass

    def _set_stratum_defaults(self, morph):
        for spec in morph['chunks']:
            if 'name' not in spec:
                spec['name'] = spec['repo']
            if 'build-mode' not in spec:
                spec['build-mode'] = \
                    self._static_defaults['chunk']['build-mode']
            if 'prefix' not in spec:
                spec['prefix'] = \
                    self._static_defaults['chunk']['prefix']

    def _set_chunk_defaults(self, morph):
        if morph['max-jobs'] is not None:
            morph['max-jobs'] = int(morph['max-jobs'])

    def lookup_build_system(self, name):
        return self._predefined_build_systems[name]

    def set_commands(self, morph):
        if morph['kind'] == 'chunk':
            default = self._static_defaults['chunk']['build-system']
            bs_name = morph.get('build-system', default)

            try:
                bs = self.lookup_build_system(bs_name)
            except KeyError:
                raise UnknownBuildSystemError(bs_name, morph['name'])

            for key in self._static_defaults['chunk']:
                if 'commands' not in key: continue
                if key not in morph:
                    attr = '_'.join(key.split('-'))
                    morph[key] = getattr(bs, attr)
