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
        '''Create a visualisation of build dependencies in a system.

        Command line arguments:

        * `REPO` is a repository URL.
        * `REF` is a git reference (usually branch name).
        * `MORPHOLOGY` is a system morphology.

        This produces a GraphViz DOT file representing all the build
        dependencies within a system, based on information in the
        morphologies.  The GraphViz `dot` program can then be used to
        create a graphical representation of the dependencies. This
        can be helpful for inspecting whether there are any problems in
        the dependencies.

        Example:

            morph graph-build-depends baserock:baserock/morphs master \
                devel-system-x86_64-generic > foo.dot
            dot -Tpng foo.dot > foo.png

        The above would create a picture with the build dependencies of
        everything in the development system for 64-bit Intel systems.

        GraphViz is not, currently, part of Baserock, so you need to run
        `dot` on another system.

        '''

        for repo_name, ref, filename in self.app.itertriplets(args):
            self.app.status(msg='Creating build order for '
                                '%(repo_name)s %(ref)s %(filename)s',
                            repo_name=repo_name, ref=ref, filename=filename)
            builder = morphlib.buildcommand.BuildCommand(self.app)
            srcpool = build_command.create_source_pool(repo_name, ref,
                                                       filename)
            root_artifact = build_command.resolve_artifacts(srcpool)

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
                for a in root_artifact.walk():
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

