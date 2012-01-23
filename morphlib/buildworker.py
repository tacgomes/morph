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


import datetime
from multiprocessing import Manager, Process

import morphlib


class BuildWorker(object):

    def __init__(self, name, app):
        self.name = name
        self.settings = app.settings
        self.real_msg = app.msg
        self.indent = 2
        self.idle_since = datetime.datetime.now()

    def __str__(self):
        return self.name

    def indent_more(self):
        self.indent += 1

    def indent_less(self):
        self.indent -= 1

    def msg(self, text):
        spaces = '  ' * self.indent
        self.real_msg('%s%s' % (spaces, text))

    def build(self, blob):
        raise NotImplementedError

    def check_complete(self, timeout):
        raise NotImplementedError


class LocalBuildWorker(BuildWorker):

    def __init__(self, name, app):
        BuildWorker.__init__(self, name, app)
        self.manager = Manager()
        self.reset()

    def reset(self):
        self.process = None
        self.blob = None
        self._output = self.manager.list()

    def run(self, repo, ref, filename, output):
        ex = morphlib.execute.Execute('.', self.msg)
        stdout = ex.runv(['./morph', '--verbose', '--keep-path',
                          'build', repo, ref, filename])
        output.append(stdout)

    def build(self, blob):
        self.reset()
        self.blob = blob
        args = (blob.morph.treeish.original_repo,
                blob.morph.treeish.ref,
                blob.morph.filename,
                self._output)
        self.process = Process(group=None, target=self.run, args=args)
        self.process.start()

    def check_complete(self, timeout):
        if self.process:
            self.process.join(timeout)
            if self.process.is_alive():
                return False
            else:
                self.idle_since = datetime.datetime.now()
                return True
        else:
            return True

    @property
    def output(self):
        return self._output[0]


class RemoteBuildWorker(BuildWorker):

    def __init__(self, app):
        BuildWorker.__init__(self, app)
