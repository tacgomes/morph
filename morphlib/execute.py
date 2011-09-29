# Copyright (C) 2011  Codethink Limited
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License.
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

    pass


class Execute(object):

    '''Execute commands for morph.'''
    
    def __init__(self, dirname, msg):
        self._setup_env()
        self.dirname = dirname
        self.msg = msg

    def _setup_env(self):
        self.env = dict(os.environ)

    def run(self, commands):
        '''Execute a list of commands.
        
        If a command fails (returns non-zero exit code), the rest are
        not run, and CommandFailure is returned.
        
        '''

        stdouts = []
        for command in commands:
            self.msg('# %s' % command)
            p = subprocess.Popen([command], shell=True,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 env=self.env,
                                 cwd=self.dirname)
            out, err = p.communicate()
            logging.debug('Exit code: %d' % p.returncode)
            logging.debug('Standard output:\n%s' % morphlib.util.indent(out))
            logging.debug('Standard error:\n%s' % morphlib.util.indent(err))
            if p.returncode != 0:
                raise CommandFailure('Command failed: %s\n%s' % 
                                      (command, morphlib.util.indent(err)))
            stdouts.append(out)
        return stdouts

    def runv(self, argv):
        '''Run a command given as a list of argv elements.
        
        Return standard output. Raise ``CommandFailure`` if the command
        fails. Log standard output and error in any case.
        
        '''

        self.msg('# %s' % ' '.join(argv))
        p = subprocess.Popen(argv, stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE, cwd=self.dirname)
        out, err = p.communicate()
        
        logging.debug('Exit code: %d' % p.returncode)
        logging.debug('Standard output:\n%s' % morphlib.util.indent(out))
        logging.debug('Standard error:\n%s' % morphlib.util.indent(err))
        if p.returncode != 0:
            raise CommandFailure('Command failed: %s\n%s' % 
                                  (argv, morphlib.util.indent(err)))
        return out

