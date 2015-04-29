# -*- coding: utf-8 -*-
# Copyright © 2015  Codethink Limited
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


from cliapp import AppException as _AppException


from .util import word_join_list as _word_join_list


def _split(iterable, split_token):
    sequence = []
    for token in iterable:
        if token == split_token:
            yield tuple(sequence)
            sequence = []
        else:
            sequence.append(token)
    if sequence:
        yield tuple(sequence)


definition_list_synopsis = 'REPO REF [PATH]...'


def definition_lists_synopsis(sep='-', at_least=0, at_most=None):
    one = definition_list_synopsis
    res = '{rest}'

    # If we may have none, then we have to mark the whole expression as
    # optional, as the trailing separator may be omitted. Otherwise we could
    # just list as many `REPO REF [PATH]... -` sequences as necessary.
    if at_least == 0:
        res = res.format(rest='[{rest}]')
    res = res.format(rest=('{one}{{rest}} [{sep}]'.format(one=one, sep=sep)))

    # Insert extra mandatory entries
    for i in xrange(at_least - 1):
        res = res.format(rest=' {sep} {one}{{rest}}'.format(sep=sep, one=one))

    # Add a variadic many if we have no maximum
    if at_most is None:
        res = res.format(
            rest=' [{sep} {one}]...{{rest}}'.format(sep=sep, one=one))
    # Otherwise add as many optional entries as needed to reach the maximum
    else:
        for i in xrange(at_most - 1 - at_least):
            res = res.format(
                rest=' [{sep} {one}]{{rest}}'.format(sep=sep, one=one))

    # Terminate synopsis string interpolations
    res = res.format(rest='')

    return res


class SystemsSpecsParseWrongNumber(_AppException):
    def __init__(self, specs, definitions_names):
        self.specs = specs
        self.definitions_names = definitions_names
        msg = 'From expected definition specs {expected};'.format(
                expected=_word_join_list(map(repr, definitions_names)))
        if len(specs) < len(definitions_names):
            missing_spec_names = definitions_names[len(specs):]
            super(SystemsSpecsParseWrongNumber, self).__init__(
                '{msg} missing {missing}'.format(
                    msg=msg,
                    missing=_word_join_list(map(repr, missing_spec_names))))
        else:
            super(SystemsSpecsParseWrongNumber, self).__init__(
                '{msg} {extra} extra specs given'.format(
                    msg=msg,
                    extra=len(specs) - len(definitions_names)))


class SystemsSpecsParseWrongFormat(_AppException):
    def __init__(self, names, malformed_definition_lists):
        self.names = names
        self.malformed_definition_lists = malformed_definition_lists
        errors = []
        for spec, name, i in malformed_definition_lists:
            pre = 'Spec {i} named {name!r}'.format(i=i, name=name)
            if not spec:
                errors.append('{} is empty, want {}'.format(
                        pre, definition_list_synopsis))
            elif len(spec) == 1:
                errors.append('{} missing REF, want {}'.format(
                        pre, definition_list_synopsis))
        super(SystemsSpecsParseWrongFormat, self).__init__(
            'From expected definition specs {expected}:\n\t{errors}'.format(
                expected=_word_join_list(map(repr, names)),
                errors='\n\t'.join(errors)))


def parse_definition_lists(args, names, sep='-'):
    '''Parse definition lists, raising Exceptions for invalid input.

    Raises a SystemsSpecsParseWrongNumber if the number of definition lists is
    not the same as the number of names.

    Raises a SystemsSpecsParseWrongFormat if any of the definition lists is too
    short to be valid.

    parse_definition_lists(args=['.', 'HEAD', 'foo.morph', '-',
                                 '../def2', 'HEAD', '-'],
                           names=('from', 'to'))
    --> ('.', 'HEAD', ('foo.morph',)), ('../def2', 'HEAD', ())
    '''
    # NOTE: To extend this to support arbitrary length definition lists, such
    #       as a list of systems to build, the best approach may be to allow it
    #       to be passed an infinite generator, used for reporting names, skip
    #       the size check if it's not an instance of Sized, and adapt the code
    #       to handle being given an infinite list, by using izip and islice so
    #       the length of the args sequence is used instead.
    specs = tuple(_split(args, sep))
    if len(specs) != len(names):
        raise SystemsSpecsParseWrongNumber(specs, names)

    malformed_definition_lists = []
    specinfo = enumerate(zip(names, specs), start=1)
    for i, (definition_list_name, definitions_spec) in specinfo:
        if len(definitions_spec) < 2:
            malformed_definition_lists.append(
                (definitions_spec, definition_list_name, i))
    if malformed_definition_lists:
        raise SystemsSpecsParseWrongFormat(names,
                                           malformed_definition_lists)

    return ((spec[0], spec[1], spec[2:]) for spec in specs)
