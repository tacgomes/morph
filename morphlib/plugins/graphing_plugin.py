# Copyright (C) 2012, 2013  Codethink Limited
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


import cliapp
import os

import morphlib


class GraphingPlugin(cliapp.Plugin):

    def enable(self):
        self.app.add_subcommand('graph-build-depends',
                                self.graph_build_depends,
                                arg_synopsis='REPO REF MORPHOLOGY')

    def disable(self):
        pass

    def graph_build_depends(self, args):
        '''Create a visualisation of build dependencies in a stratum'''
        for repo_name, ref, filename in self.app.itertriplets(args):
            self.app.status(msg='Creating build order for '
                                '%(repo_name)s %(ref)s %(filename)s',
                            repo_name=repo_name, ref=ref, filename=filename)
            builder = morphlib.buildcommand.BuildCommand(self.app)
            artifact = builder.get_artifact_object(repo_name, ref, filename)

            basename, ext = os.path.splitext(filename)
            dot_filename = basename + '.gv'
            dep_fmt = '  "%s" -> "%s";\n'
            shape_name = {
                'system': 'octagon',
                'stratum': 'box',
                'chunk': 'ellipse',
            }

            self.app.status(msg='Writing DOT file to %(filename)s',
                            filename=dot_filename)

            with open(dot_filename, 'w') as f:
                f.write('digraph "%s" {\n' % basename)
                for a in artifact.walk():
                    f.write(
                        '  "%s" [shape=%s];\n' %
                        (a.name,
                         shape_name[a.source.morphology['kind']]))
                    for dep in a.dependencies:
                        if a.source.morphology['kind'] == 'stratum':
                            if dep.dependents == [a]:
                                f.write(dep_fmt %
                                        (a.name, dep.name))
                        else:
                            f.write(dep_fmt % (a.name, dep.name))
                f.write('}\n')

