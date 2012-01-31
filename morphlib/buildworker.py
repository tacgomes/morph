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

    def __init__(self, name, ident, app):
        self.name = name
        self.ident = ident
        self.settings = app.settings
        self.real_msg = app.msg
        self.indent = 2
        self.idle_since = datetime.datetime.now()
        self.manager = Manager()
        self.reset()

    def indent_more(self): # pragma: no cover
        self.indent += 1

    def indent_less(self): # pragma: no cover
        self.indent -= 1

    def msg(self, text): # pragma: no cover
        spaces = '  ' * self.indent
        self.real_msg('%s%s' % (spaces, text))

    def reset(self):
        self.process = None
        self.blob = None
        self._output = self.manager.list()
        self._error = self.manager.dict()

    def build(self, blob):
        raise NotImplementedError

    def check_complete(self, timeout): # pragma: no cover
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
        try:
            return self._output[0]
        except IndexError:
            return None

    @property
    def error(self):
        return self._error

    def options(self): # pragma: no cover
        '''Returns an array of command line options for the settings.
        
        NOTE: This is just a hack that uses internals of the cliapp.Settings
        class. We need to merge this kind of functionality into cliapp and
        remove this hack!
        
        '''

        # use the canonical names of the settings to generate cmdline options
        names = list(self.settings._canonical_names)

        # internal function to combine an option name and a value into string
        def combine(name, value):
            if name.startswith('--'):
                if isinstance(value, bool):
                    if value:
                        return '%s' % name
                else:
                    return '%s=%s' % (name, value)
            else:
                if isinstance(value, bool):
                    if value:
                        return '%s' % name
                else:
                    return '%s %s' % (name, value)

        # generate a list of (setting name, option name) pairs
        options_list = []
        options = self.settings._option_names(names)
        name_pairs = [(names[i], options[i]) for i in xrange(0, len(names))]

        # convert all settings into command line arguments; drop absent
        # settings and make sure to convert all values correctly
        for name, option in name_pairs:
            value = self.settings[name]
            if isinstance(value, list):
                for listval in value:
                    if isinstance(listval, str):
                        if len(listval) > 0:
                            string = combine(option, listval)
                            if string:
                                options_list.append(string)
                    else:
                        string = combine(option, listval)
                        if string:
                            options_list.append(string)
            else:
                if isinstance(value, str):
                    if len(value) > 0:
                        string = combine(option, value)
                        if string:
                            options_list.append(string)
                else:
                    string = combine(option, value)
                    if string:
                        options_list.append(string)
        return options_list

    def __str__(self):
        return self.name


class LocalBuildWorker(BuildWorker):

    def __init__(self, name, ident, app):
        BuildWorker.__init__(self, name, ident, app)

    def run(self, first_tuple, second_tuple, sudo, output,
            error): # pragma: no cover
        ex = morphlib.execute.Execute('.', self.msg)

        # generate command line options
        args = self.options()
        cmdline = []
        if sudo:
            cmdline.extend(['sudo'])
        cmdline.extend(['morph', 'build-single'])
        cmdline.extend([first_tuple['repo'],
                        first_tuple['ref'],
                        first_tuple['filename']])
        if second_tuple:
            cmdline.extend([second_tuple['repo'],
                            second_tuple['ref'],
                            second_tuple['filename']])
        cmdline.extend(args)

        # run morph locally in a child process
        try:
            stdout = ex.runv(cmdline)
            output.append(stdout)
        except OSError, e:
            error['error'] = str(e)
            error['command'] = ' '.join(cmdline)
        except morphlib.execute.CommandFailure, e:
            error['error'] = str(e)
            error['command'] = ' '.join(cmdline)
        
    def build(self, blob): # pragma: no cover
        self.reset()
        self.blob = blob

        first_tuple = None
        if len(blob.parents) > 0:
            first_tuple = {
                'repo': blob.parents[0].morph.treeish.original_repo,
                'ref': blob.parents[0].morph.treeish.ref,
                'filename': blob.parents[0].morph.filename,
            }

        blob_tuple = {
            'repo': blob.morph.treeish.original_repo,
            'ref': blob.morph.treeish.ref,
            'filename': blob.morph.filename,
        }

        args = (first_tuple if first_tuple else blob_tuple,
                blob_tuple if first_tuple else None,
                blob.morph.kind == 'system',
                self._output,
                self._error)
        self.process = Process(group=None, target=self.run, args=args)
        self.process.start()


class RemoteBuildWorker(BuildWorker):

    def __init__(self, name, ident, app):
        BuildWorker.__init__(self, name, ident, app)
        self.hostname = ident

    def run(self, first_tuple, second_tuple, sudo, output,
            error): # pragma: no cover
        ex = morphlib.execute.Execute('.', self.msg)

        # generate command line options
        args = self.options()
        cmdline = ['ssh', '-q', self.hostname]
        if sudo:
            cmdline.extend(['-t', '-t', '-t', 'sudo', '-S',
                            'bash', '--login', '-c'])
            cmdline.extend(['"'])
            cmdline.extend(['morph', 'build-single', repo, ref, filename])
            cmdline.extend([first_tuple['repo'],
                            first_tuple['ref'],
                            first_tuple['filename']])
            if second_tuple:
                cmdline.extend([second_tuple['repo'],
                                second_tuple['ref'],
                                second_tuple['filename']])
            cmdline.extend(args)
            cmdline.extend(['"'])
        else:
            cmdline.extend(['fakeroot'])
            cmdline.extend(['morph', 'build-single', repo, ref, filename])
            cmdline.extend([first_tuple['repo'],
                            first_tuple['ref'],
                            first_tuple['filename']])
            if second_tuple:
                cmdline.extend([second_tuple['repo'],
                                second_tuple['ref'],
                                second_tuple['filename']])
            cmdline.extend(args)

        # run morph on the other machine
        try:
            stdout = ex.runv(cmdline)
            output.append(stdout)
        except OSError, e:
            error['error'] = str(e)
            error['command'] = ' '.join(cmdline)
        except morphlib.execute.CommandFailure, e:
            error['error'] = str(e)
            error['command'] = ' '.join(cmdline)
        
    def build(self, blob): # pragma: no cover
        self.reset()
        self.blob = blob

        first_tuple = None
        if len(blob.parents) > 0:
            first_tuple = {
                'repo': blob.parents[0].morph.treeish.original_repo,
                'ref': blob.parents[0].morph.treeish.ref,
                'filename': blob.parents[0].morph.filename,
            }

        blob_tuple = {
            'repo': blob.morph.treeish.original_repo,
            'ref': blob.morph.treeish.ref,
            'filename': blob.morph.filename,
        }

        args = (first_tuple if first_tuple else blob_tuple,
                blob_tuple if first_tuple else None,
                blob.morph.kind == 'system',
                self._output,
                self._error)
        self.process = Process(group=None, target=self.run, args=args)
        self.process.start()
