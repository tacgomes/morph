
import os
import sys
import jsonschema
import yaml
import morphlib
import cliapp

def _create_whereindoc_string(whereindoc):
    string = whereindoc[0]
    for v in whereindoc[1:]:
        if isinstance(v, basestring):
            string += ".{key}".format(key=v)
        elif isinstance(v, int):
            string += "[{index}]".format(index=v)
    return string

class MissingRequiredPropertyError(cliapp.AppException):
    def __init__(self, filepath, field, path):
        path_string = _create_whereindoc_string(path)
        self.msg = "%s: required property `%s' is missing on %s" % (
                filepath, field, path_string)


class UnknownPropertyError(cliapp.AppException):
    def __init__(self, filepath, field, whereindoc):
        whereindoc = _create_whereindoc_string(whereindoc)
        self.msg = ("{filepath}: property `{field}' is unknown on "
                   "{whereindoc}").format(filepath=filepath,
                                          field=field,
                                          whereindoc=whereindoc)


class TypeMismatchError(cliapp.AppException):
    def __init__(self, filepath, type, whereindoc):
        whereindoc = _create_whereindoc_string(whereindoc)
        self.msg = "{filepath}: type mismatch ({type} expected) on " \
                   "{whereindoc}".format(filepath=filepath,
                                         type=type,
                                         whereindoc=whereindoc)


class InvalidValueError(cliapp.AppException):
    def __init__(self, filepath, reason, whereindoc):
        whereindoc = _create_whereindoc_string(whereindoc)
        self.msg = "{filepath}: invalid value ({reason}) on " \
                   "{whereindoc}".format(filepath=filepath,
                                         reason=reason,
                                         whereindoc=whereindoc)


class JSONSchemaValidator(object):

    def __init__(self, document, schema, docfilepath=None):
        self._document = yaml.load(document)
        self._schema = yaml.load(schema)
        self._docfilename = docfilepath

    @classmethod
    def from_file(cls, document_filepath, schema_filepath): # pragma: no cover
        with open(document_filepath) as f:
            document = f.read()

        with open(schema_filepath) as f:
            schema = f.read()

        return cls(document, schema, document_filepath)

    def validate_string(self, obj, schema, whereindoc):
        if not isinstance(obj, basestring):
            raise TypeMismatchError(self._docfilename, 'string', whereindoc)
        # TODO format

    def validate_integer(self, obj, schema, whereindoc):
        if not isinstance(obj, (int, long)):
            raise TypeMismatchError(self._docfilename, 'integer', whereindoc)

    def validate_array(self, array, schema, definitions, whereindoc):
        if not isinstance(array, list):
            raise TypeMismatchError(self._docfilename, 'list', whereindoc)

    def validate_enum(self, obj, schema, whereindoc):
        if not isinstance(obj, basestring):
            raise TypeMismatchError(self._docfilename, 'string', whereindoc)
        if obj not in schema['enum']:
            reason="'{value}' is not in the enumeration {enum}".format(
                    value=obj, enum=schema['enum'])
            raise InvalidValueError(self._docfilename, reason, whereindoc)

    def validate(self, document, schema, definitions, path):
        if 'type' in schema:
            if schema['type'] == 'object':
                pass
            elif schema['type'] == 'integer':
                self.validate_integer(document, schema, path)
            elif schema['type'] == 'string':
                self.validate_string(document, schema, path)
            elif schema['type'] == 'array':
                self.validate_array(document, schema, definitions, path)
                for idx, element in enumerate(document):
                    self.validate(element, schema['items'], definitions,
                            path + [idx])
            else:
                raise Exception("Error: type is n") # pragma: no cover
        elif 'enum' in schema:
            self.validate_enum(document, schema, path)
        elif '$ref' in schema:
            subschema = definitions[schema['$ref'].split('/')[-1]]
            self.validate(document, subschema, definitions, path)
        else:
            raise Exception("Error: type is notd 2") # pragma: no cover

        for prop in schema.get('properties') or []:
            if prop in document:
                self.validate(document[prop], schema['properties'][prop],
                        definitions, path + [prop])
            else:
                if prop in schema.get('required', []):
                    raise MissingRequiredPropertyError(self._docfilename,
                            prop, path)

        # TODO patternProperties

        additional_props = schema.get('additionalProperties', True)
        if not additional_props:
            for field in document:
                if field not in (schema.get('properties') or []):
                    raise UnknownPropertyError(self._docfilename, field,
                            path)

    def validate_document(self):
        treeroot, _ = os.path.splitext(os.path.basename(self._docfilename))
        self.validate(self._document,
                      self._schema,
                      self._schema.get('definitions', {}),
                      [treeroot])


if __name__ == '__main__': # pragma: no cover
    validator = JSONSchemaValidator.from_file(sys.argv[1], sys.argv[2])
    validator.validate_document()
