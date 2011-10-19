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


import logging
import os
import subprocess

import morphlib


class CommandFailure(Exception):

    def __init__(self, command, stdout, stderr, exit):
        Exception.__init__(self,
                           'Command failed: %s\n'
                           'Standard output:\n%s\n'
                           'Standard error:\n%s\n'
                           'Exit code: %s' % 
                             (command,
                              morphlib.util.indent(stdout),
                              morphlib.util.indent(stderr),
                              exit))
        


class Execute(object):

    '''Execute commands for morph.'''
    
    def __init__(self, dirname, msg):
        self._setup_env()
        self.dirname = dirname
        self.msg = msg

    def _setup_env(self):
        self.env = dict(os.environ)

    def run(self, commands, as_root=False, as_fakeroot=False):
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
                                 stderr=subprocess.PIPE,
                                 env=self.env,
                                 cwd=self.dirname)
            out, err = p.communicate()
            logging.debug('Exit code: %d' % p.returncode)
            logging.debug('Standard output:\n%s' % morphlib.util.indent(out))
            logging.debug('Standard error:\n%s' % morphlib.util.indent(err))
            if p.returncode != 0:
                raise CommandFailure(command, out, err, p.returncode)
            stdouts.append(out)
        return stdouts

    def runv(self, argv, as_root=False, as_fakeroot=False):
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
                             stderr=subprocess.PIPE, cwd=self.dirname)
        out, err = p.communicate()
        
        logging.debug('Exit code: %d' % p.returncode)
        logging.debug('Standard output:\n%s' % morphlib.util.indent(out))
        logging.debug('Standard error:\n%s' % morphlib.util.indent(err))
        if p.returncode != 0:
            raise CommandFailure(' '.join(argv), out, err, p.returncode)
        return out

