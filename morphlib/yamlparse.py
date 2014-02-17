# Copyright (C) 2013-2014  Codethink Limited
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

    def load(*args, **kwargs):
        return yaml.safe_load(*args, **kwargs)

    def dump(*args, **kwargs):
        if 'default_flow_style' not in kwargs:
            kwargs['default_flow_style'] = False
        return yaml.dump(Dumper=morphlib.morphloader.OrderedDumper,
                         *args, **kwargs)

else: # pragma: no cover
    def load(*args, **kwargs):
        raise morphlib.Error('YAML not available')
    def dump(*args, **kwargs):
        raise morphlib.Error('YAML not available')
