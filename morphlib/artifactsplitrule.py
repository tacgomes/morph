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


import collections
import itertools
import re

import morphlib


class Rule(object):
    '''Rule base class.

    Rules are passed an object and are expected to determine whether
    it matches. It's roughly the same machinery for matching files
    as artifacts, it's just that Files are given just the path, while
    Artifact matches are given the artifact name and the name of the
    source it came from.

    '''

    def match(self, *args):
        return True


class FileMatch(Rule):
    '''Match a file path against a list of regular expressions.

    If the path matches any of the regular expressions, then the file
    is counted as a valid match.

    '''

    def __init__(self, regexes):
        # Possible optimisation: compile regexes as one pattern
        self._regexes = [re.compile(r) for r in regexes]

    def match(self, path):
        return any(r.match(path) for r in self._regexes)

    def __repr__(self):
        return 'FileMatch(%s)' % '|'.join(r.pattern for r in self._regexes)


class ArtifactMatch(Rule):
    '''Match an artifact's name against a list of regular expressions.
    '''

    def __init__(self, regexes):
        # Possible optimisation: compile regexes as one pattern
        self._regexes = [re.compile(r) for r in regexes]

    def match(self, (source_name, artifact_name)):
        return any(r.match(artifact_name) for r in self._regexes)

    def __repr__(self):
        return 'ArtifactMatch(%s)' % '|'.join(r.pattern for r in self._regexes)


class ArtifactAssign(Rule):
    '''Match only artifacts with the specified source and artifact names.

    This is a valid match if the source and artifact names exactly match.
    This is used for explicit artifact assignment e.g. chunk artifact
    foo-bins which comes from chunk source foo goes into stratum
    bar-runtime.

    '''

    def __init__(self, source_name, artifact_name):
        self._key = (source_name, artifact_name)

    def match(self, (source_name, artifact_name)):
        return (source_name, artifact_name) == self._key

    def __repr__(self):
        return 'ArtifactAssign(%s, %s)' % self._key


class SourceAssign(Rule):
    '''Match only artifacts which come from the specified source.

    This is a valid match only if the artifact comes from the specified
    source. e.g. all artifacts produced by source bar-runtime go into
    system baz

    '''

    def __init__(self, source_name):
        self._source = source_name

    def match(self, (source_name, artifact_name)):
        return source_name == self._source

    def __repr__(self):
        return 'SourceAssign(%s, *)' % self._source


class SplitRules(collections.Iterable):
    '''Rules engine for splitting a source's artifacts.

    Rules are added with the .add(artifact, rule) method, though another
    SplitRules may be created by passing a SplitRules to the constructor.

    .match(path|(source, artifact)) and .partition(iterable) are used
    to determine if an artifact matches the rules. Rules are processed
    in order, so more specific matches first can be followed by more
    generic catch-all matches.

    '''

    def __init__(self, *args):
        self._rules = list(*args)

    def __iter__(self):
        return iter(self._rules)

    def add(self, artifact, rule):
        self._rules.append((artifact, rule))

    @property
    def artifacts(self):
        '''Get names of all artifacts in the rule set.

        Returns artifact names in the order they were added to the rules,
        and not repeating the artifact.

        '''

        seen = set()
        result = []
        for artifact_name, rule in self._rules:
            if artifact_name not in seen:
                seen.add(artifact_name)
                result.append(artifact_name)
        return result

    def match(self, *args):
        '''Return all artifact names the given argument matches.

        It's returned in match order as a list, so it's possible to
        detect overlapping matches, even though most of the time, the
        only used entry will be the first.

        '''

        return [a for a, r in self._rules if r.match(*args)]

    def partition(self, iterable):
        '''Match many files or artifacts.

        This function takes an iterable of file names, and groups them
        using the rules that have been added to this object.

        This is a convenience function that uses the match() method internally.

        '''

        matches = collections.defaultdict(list)
        overlaps = collections.defaultdict(set)
        unmatched = set()

        for arg in iterable:
            matched = self.match(arg)
            if len(matched) == 0:
                unmatched.add(arg)
                continue
            if len(matched) != 1:
                overlaps[arg].update(matched)
            matches[matched[0]].append(arg)

        return matches, overlaps, unmatched

    def __repr__(self):
        return 'SplitRules(%s)' % ', '.join(
            '%s=%s' % (artifact, rule)
            for artifact, rule in  self._rules)


# A 'no-op' set of split rules. An empty list would cause everything to be
# ignored, which is unlikely to ever be what a user wants, and breaks some
# internal bits of Morph.
EMPTY_RULES = [
    ('', [r'.*'])
]


def unify_chunk_matches(morphology, default_rules=None):
    '''Create split rules including defaults and per-chunk rules.

    With rules specified in the morphology's 'products' field and the
    default rules for chunks, generate rules to match the files produced
    by building the chunk to the chunk artifact they should be put in.

    '''
    if default_rules is None or len(default_rules) == 0:
        default_rules = EMPTY_RULES

    split_rules = SplitRules()

    for ca_name, patterns in ((d['artifact'], d['include'])
                              for d in morphology['products']):
        split_rules.add(ca_name, FileMatch(patterns))

    name = morphology['name']
    for suffix, patterns in default_rules:
        ca_name = name + suffix
        # Explicit rules override the default rules. This is an all-or-nothing
        # override: there is no way to extend the default split rules right now
        # without duplicating them in the chunk morphology.
        if ca_name not in split_rules.artifacts:
            split_rules.add(ca_name, FileMatch(patterns))

    return split_rules


def unify_stratum_matches(morphology, default_rules=None):
    '''Create split rules including defaults and per-stratum rules.

    With rules specified in the chunk spec's 'artifacts' fields, the
    stratum's 'products' field and the default rules for strata, generate
    rules to match the artifacts produced by building the chunks in the
    strata to the stratum artifact they should be put in.

    '''
    if default_rules is None or len(default_rules) == 0:
        default_rules = EMPTY_RULES

    assignment_split_rules = SplitRules()
    for spec in morphology['chunks']:
        source_name = spec['name']
        for ca_name, sta_name in sorted(spec.get('artifacts', {}).iteritems()):
            assignment_split_rules.add(sta_name,
                                       ArtifactAssign(source_name, ca_name))

    # Construct match rules separately, so we can use the SplitRules object's
    # own knowledge of which rules already exist to determine whether
    # to include the default rule.
    # Rather than use the existing SplitRules, use a new one, since
    # match rules suppliment assignment rules, rather than replace.
    match_split_rules = SplitRules()
    for sta_name, patterns in ((d['artifact'], d['include'])
                               for d in morphology.get('products', {})):
        match_split_rules.add(sta_name, ArtifactMatch(patterns))

    for suffix, patterns in default_rules:
        sta_name = morphology['name'] + suffix
        # Explicit rules override the default rules. This is an all-or-nothing
        # override: there is no way to extend the default split rules right now
        # without duplicating them in the chunk morphology.
        if sta_name not in match_split_rules.artifacts:
            match_split_rules.add(sta_name, ArtifactMatch(patterns))

    # Construct a new SplitRules with the assignments before matches
    return SplitRules(itertools.chain(assignment_split_rules,
                                      match_split_rules))


def unify_system_matches(morphology, default_rules=None):
    '''Create split rules including defaults and per-chunk rules.

    With rules specified in the morphology's 'products' field and the
    default rules for chunks, generate rules to match the files produced
    by building the chunk to the chunk artifact they should be put in.

    '''

    name = morphology['name'] + '-rootfs'
    split_rules = SplitRules()

    for spec in morphology['strata']:
        source_name = spec.get('name', spec['morph'])
        if spec.get('artifacts', None) is None:
            split_rules.add(name, SourceAssign(source_name))
            continue
        for sta_name in spec['artifacts']:
            split_rules.add(name, ArtifactAssign(source_name, sta_name))

    return split_rules


def unify_cluster_matches(_):
    return SplitRules()
