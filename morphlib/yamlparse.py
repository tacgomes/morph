# Copyright (C) 2013  Codethink Limited
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


import morphlib
from morphlib.util import OrderedDict

if morphlib.got_yaml: # pragma: no cover
    yaml = morphlib.yaml


if morphlib.got_yaml: # pragma: no cover

    class OrderedDictYAMLLoader(yaml.SafeLoader):
        """A YAML loader that loads mappings into ordered dictionaries.

       When YAML is loaded with this Loader, it loads mappings as ordered
       dictionaries, so the order the keys were written in is maintained.

       When combined with the OrderedDictYAMLDumper, this allows yaml documents
       to be written out in a similar format to they were read.

        """

        def __init__(self, *args, **kwargs):
            yaml.SafeLoader.__init__(self, *args, **kwargs)

            # When YAML encounters a mapping (which YAML identifies with
            # the given tag), it will use construct_yaml_map to read it as
            # an OrderedDict.
            self.add_constructor(u'tag:yaml.org,2002:map',
                                 type(self).construct_yaml_map)

        def construct_yaml_map(self, node):
            data = OrderedDict()
            yield data
            value = self.construct_mapping(node)
            data.update(value)

        def construct_mapping(self, node, deep=False):
            if isinstance(node, yaml.MappingNode):
                self.flatten_mapping(node)
            else:
                raise yaml.constructor.ConstructorError(
                    None, None,
                    'expected a mapping node, but found %s' % node.id,
                    node.start_mark)

            mapping = OrderedDict()
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                try:
                    hash(key)
                except TypeError, exc:
                    raise yaml.constructor.ConstructorError(
                        'while constructing a mapping', node.start_mark,
                        'found unacceptable key (%s)' % exc,
                        key_node.start_mark)
                value = self.construct_object(value_node, deep=deep)
                mapping[key] = value
            return mapping

    class OrderedDictYAMLDumper(yaml.SafeDumper):
        """A YAML dumper that will dump OrderedDicts as mappings.

       When YAML is dumped with this Dumper, it dumps OrderedDicts as
       mappings, preserving the key order, so the order the keys were
       written in is maintained.

       When combined with the OrderedDictYAMLDumper, this allows yaml documents
       to be written out in a similar format to they were read.

        """

        def __init__(self, *args, **kwargs):
            yaml.SafeDumper.__init__(self, *args, **kwargs)

            # When YAML sees an OrderedDict, use represent_ordered_dict to
            # dump it
            self.add_representer(OrderedDict,
                                 type(self).represent_ordered_dict)

        def represent_ordered_dict(self, odict):
            return self.represent_ordered_mapping(
                u'tag:yaml.org,2002:map', odict)

        def represent_ordered_mapping(self, tag, omap):
            value = []
            node = yaml.MappingNode(tag, value)
            if self.alias_key is not None:
                self.represented_objects[self.alias_key] = node
            best_style = True
            for item_key, item_value in omap.iteritems():
                node_key = self.represent_data(item_key)
                node_value = self.represent_data(item_value)
                if not (isinstance(node_key, yaml.ScalarNode) and
                        not node_key.style):
                    best_style = False # pragma: no cover
                if not (isinstance(node_value, yaml.ScalarNode) and
                        not node_value.style):
                    best_style = False # pragma: no cover
                value.append((node_key, node_value))
            if self.default_flow_style is not None:
                node.flow_style = self.default_flow_style
            else:
                node.flow_style = best_style # pragma: no cover
            return node

    def load(*args, **kwargs):
        return yaml.load(Loader=OrderedDictYAMLLoader, *args, **kwargs)

    def dump(*args, **kwargs):
        if 'default_flow_style' not in kwargs:
            kwargs['default_flow_style'] = False
        return yaml.dump(Dumper=OrderedDictYAMLDumper, *args, **kwargs)

else: # pragma: no cover
    def load(*args, **kwargs):
        raise morphlib.Error('YAML not available')
    def dump(*args, **kwargs):
        raise morphlib.Error('YAML not available')
