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


import unittest
import textwrap

from morphlib.jsonschemavalidator import *


class JSONSchemaValidatorTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def validate(self, document, schema):
        validator = JSONSchemaValidator

    def test_validates_string(self):
        schema = 'type: string'
        document = 'some  string'
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        v.validate_document()
        document = '1234'
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        self.assertRaises(morphlib.jsonschemavalidator.TypeMismatchError,
                v.validate_document)

    def test_validates_integer(self):
        schema = 'type: integer'
        document = '24'
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        v.validate_document()
        document = 'some string'
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        self.assertRaises(morphlib.jsonschemavalidator.TypeMismatchError,
                v.validate_document)

    def test_validates_array(self):
        schema = textwrap.dedent(r'''
        type: array
        items: {type: string}
        ''')
        document = r'[A, B, C]'
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        v.validate_document()
        document = 'names: onlyme'
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        self.assertRaises(morphlib.jsonschemavalidator.TypeMismatchError,
                v.validate_document)
        schema = textwrap.dedent(r'''
        type: array
        items: {type: string}
        ''')
        document = '[ A, 2, C]'
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        self.assertRaises(morphlib.jsonschemavalidator.TypeMismatchError,
                v.validate_document)

    def test_validates_enum(self):
        schema = 'enum: [Red, Green, Blue]'
        document = 'Red'
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        v.validate_document()
        document = 'colors: notaenum'
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        self.assertRaises(morphlib.jsonschemavalidator.TypeMismatchError,
                v.validate_document)
        schema = 'enum: [Red, Green, Blue]'
        document = 'Pink'
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        self.assertRaises(morphlib.jsonschemavalidator.InvalidValueError,
                v.validate_document)

    def test_validates_missing_required_field(self):
        schema = textwrap.dedent(r'''
        type: object
        properties:
            name: {type: string}
            kind: {type: string}
        required: ['kind']
        ''')
        document = textwrap.dedent(r'''
        name: foo
        kind: bar
        ''')
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        v.validate_document()
        document = 'name: foo'
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        self.assertRaises(
                morphlib.jsonschemavalidator.MissingRequiredPropertyError,
                v.validate_document)

    def test_validates_unkown_properties(self):
        schema = textwrap.dedent(r'''
        type: object
        properties:
          name: {type: string}
        ''')
        document = textwrap.dedent(r'''
        name: foo
        additional: property
        ''')
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        v.validate_document()
        schema = textwrap.dedent(r'''
        type: object
        properties:
          name: {type: string}
        additionalProperties: False
        ''')
        document = textwrap.dedent(r'''
        name: foo
        additional: property
        ''')
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        self.assertRaises(morphlib.jsonschemavalidator.UnknownPropertyError,
                v.validate_document)

    def test_validates_schemas_with_refs(self):
        schema = textwrap.dedent(r'''
        definitions:
          chunk-reference:
            type: object
            properties:
              repo: {type: string}
              ref: {type: string}
            required: [repo, ref]
        type: object
        properties:
          name: {type: string}
          kind: {type: string}
          chunk: {$ref: "#/definitions/chunk-reference"}
        required: ['kind']
        ''')
        document = textwrap.dedent(r'''
        name: foo
        kind: bar
        chunk:
          repo: foo
          ref: bar
        ''')
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        v.validate_document()
        document = textwrap.dedent(r'''
        name: foo
        kind: bar
        chunk:
          repo: foo
        ''')
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        self.assertRaises(
                morphlib.jsonschemavalidator.MissingRequiredPropertyError,
                v.validate_document)

    def test_validates_complex_documents(self):
        schema = textwrap.dedent(r'''
        definitions:
          chunk-reference:
            type: object
            additionalProperties: false
            required: ['repo', 'ref']
            properties:
              repo: {type: string}
              ref: {type: string}
        type: object
        properties:
          name: {type: string}
          kind: {type: string}
          chunks:
            type: array
            items:
              type: object
              additionalProperties: false
              required: ['repo', 'ref', 'commands']
              properties:
                repo: {type: string}
                ref: {type: string}
                commands:
                  type: object
                  additionalProperties: false
                  required: [buildcommands, installcommands]
                  properties:
                    buildcommands: {type: string}
                    installcommands: {type: string}
        required: ['kind']
        additionalProperties: False
        ''')
        document = textwrap.dedent(r'''
        name: foo
        kind: bar
        chunks:
        - repo: repo1
          ref: aref
          commands:
            buildcommands: foo
            installcommands: doo
        - repo: repo2
          ref: arefa
          commands:
            buildcommands: foo
            installcommands: doo
        ''')
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        v.validate_document()
        document = textwrap.dedent(r'''
        name: foo
        kind: bar
        chunks:
        - repo: repo11
          ref: arefa
          commands:
            buildcommands: foo
            installcommands: doo
        - repo: repo2
          ref: arefa
          commands:
            buildcommands: foo
        ''')
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        self.assertRaises(
                morphlib.jsonschemavalidator.MissingRequiredPropertyError,
                v.validate_document)
        document = textwrap.dedent(r'''
        name: foo
        kind: bar
        chunks:
        - repo: repo11
          ref: arefa
          commands:
            buildcommands: foo
            installcommands: doo
        - repo: repo2
          ref: arefa
          commands:
            buildcommands: foo
            installcommands: foo
            unknowncommands: foo
        ''')
        v = JSONSchemaValidator(document, schema, "documents/document.json")
        self.assertRaises(morphlib.jsonschemavalidator.UnknownPropertyError,
                v.validate_document)
