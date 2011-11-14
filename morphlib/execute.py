# Copyright (C) 2011  Codethink Limited
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
import logging
import os
import subprocess

import morphlib


class CommandFailure(cliapp.AppException):

    def __init__(self, command, stderr):
        cliapp.AppException.__init__(self, 
                'Command failed: %s\Output from command:\n%s' % 
                    (command, stderr))


class Execute(object):

    '''Execute commands for morph.'''
    
    def __init__(self, dirname, msg):
        self._setup_env()
        self.dirname = dirname
        self.msg = msg

    def _setup_env(self):
        self.env = dict(os.environ)

    def run(self, commands, as_root=False, as_fakeroot=False, _log=True):
        '''Execute a list of commands.
        
        If a command fails (returns non-zero exit code), the rest are
        not run, and CommandFailure is returned.
        
        '''

        stdouts = []
        for command in commands:
            self.msg('# %s' % command)
            argv = ['sh', '-c', command]
            if as_root:
                argv = ['sudo'] + argv # pragma: no cover
            elif as_fakeroot:
                argv = ['fakeroot'] + argv
            p = subprocess.Popen(argv, shell=False,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 env=self.env,
                                 cwd=self.dirname)
            out, err = p.communicate()
            if p.returncode != 0:
                if _log: # pragma: no cover
                    logging.error('Exit code: %d' % p.returncode)
                    logging.error('Standard output and error:\n%s' % 
                                    morphlib.util.indent(out))
                raise CommandFailure(command, out)
            stdouts.append(out)
        return stdouts

    def runv(self, argv, as_root=False, as_fakeroot=False, _log=True):
        '''Run a command given as a list of argv elements.
        
        Return standard output. Raise ``CommandFailure`` if the command
        fails. Log standard output and error in any case.
        
        '''

        if as_root:
            argv = ['sudo'] + argv # pragma: no cover
        elif as_fakeroot:
            argv = ['fakeroot'] + argv
        self.msg('# %s' % ' '.join(argv))
        p = subprocess.Popen(argv, stdout=subprocess.PIPE, 
                             stderr=subprocess.STDOUT, cwd=self.dirname)
        out, err = p.communicate()
        
        if p.returncode != 0:
            if _log: # pragma: no cover
                logging.error('Exit code: %d' % p.returncode)
                logging.error('Standard output and error:\n%s' % 
                                morphlib.util.indent(out))
            raise CommandFailure(' '.join(argv), out)
        return out

