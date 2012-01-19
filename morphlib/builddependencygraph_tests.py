# Copyright (C) 2012  Codethink Limited
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


import unittest

import morphlib


class BuildDependencyGraphTests(unittest.TestCase):

    def test_node_add_remove_dependency(self):
        node1 = morphlib.blobs.Blob(None)
        node2 = morphlib.blobs.Blob(None)

        node1.add_dependency(node2)

        assert(node2 in node1.dependencies)
        assert(node1 in node2.dependents)
        
        assert(node1.depends_on(node2))

        node2.add_dependency(node1)

        assert(node2 in node1.dependencies)
        assert(node1 in node2.dependents)
        assert(node1 in node2.dependencies)
        assert(node2 in node1.dependents)

        assert(node1.depends_on(node2))
        assert(node2.depends_on(node1))

        node1.remove_dependency(node2)

        assert(node2 not in node1.dependencies)
        assert(node1 not in node2.dependents)
        assert(node1 in node2.dependencies)
        assert(node2 in node1.dependents)

        assert(not node1.depends_on(node2))
        assert(node2.depends_on(node1))

        node2.remove_dependency(node1)

        assert(node2 not in node1.dependencies)
        assert(node1 not in node2.dependents)
        assert(node1 not in node2.dependencies)
        assert(node2 not in node1.dependents)

        assert(not node1.depends_on(node2))
        assert(not node2.depends_on(node1))
