# Copyright (C) 2011-2012  Codethink Limited
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
                'Command failed: %s\nOutput from command:\n%s' % 
                    (command, stderr))


class Execute(object):

    '''Execute commands for morph.'''
    
    def __init__(self, dirname, msg):
        self._setup_env()
        self.dirname = dirname
        self.msg = msg

    def _setup_env(self):
        self.env = dict(os.environ)

    def run(self, commands, _log=True):
        '''Execute a list of commands.
        
        If a command fails (returns non-zero exit code), the rest are
        not run, and CommandFailure is returned.
        
        '''

        stdouts = []
        for command in commands:
            self.msg('# %s' % command)
            argv = ['sh', '-c', command]
            logging.debug('run: argv=%s' % repr(argv))
            logging.debug('run: env=%s' % repr(self.env))
            logging.debug('run: cwd=%s' % repr(self.dirname))
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

    def runv(self, argv, feed_stdin=None, _log=True, **kwargs):
        '''Run a command given as a list of argv elements.
        
        Return standard output. Raise ``CommandFailure`` if the command
        fails. Log standard output and error in any case.
        
        '''
        if 'stdout' not in kwargs:
            kwargs['stdout'] = subprocess.PIPE
        if feed_stdin is not None and 'stdin' not in kwargs: 
            kwargs['stdin'] = subprocess.PIPE # pragma: no cover
        if 'stderr' not in kwargs:
            kwargs['stderr'] = subprocess.STDOUT
        if 'cwd' not in kwargs:
            kwargs['cwd'] = self.dirname
        if 'env' not in kwargs:
            kwargs['env'] = self.env

        logging.debug('runv: argv=%s' % repr(argv))
        logging.debug('runv: env=%s' % repr(kwargs['env']))
        logging.debug('runv: cwd=%s' % repr(self.dirname))
        self.msg('# %s' % ' '.join(argv))
        p = subprocess.Popen(argv, **kwargs)
        out, err = p.communicate(feed_stdin)
        
        if _log: # pragma: no cover
            if p.returncode == 0:
                logger = logging.debug
            else:
                logger = logging.error
            logger('Exit code: %d' % p.returncode)
            logger('Standard output:\n%s' % morphlib.util.indent(out or ''))
            logger('Standard error:\n%s' % morphlib.util.indent(err or ''))
        if p.returncode != 0:
            raise CommandFailure(' '.join(argv), out)
        else:
            return out

