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


import binascii
import cliapp
import ConfigParser
import logging
import os
import re
import StringIO

import cliapp

import morphlib


class NoModulesFileError(cliapp.AppException):

    def __init__(self, repo, ref):
        Exception.__init__(self, 
                           '%s:%s has no .gitmodules file.' % (repo, ref))


class Submodule(object):

    def __init__(self, name, url, path):
        self.name = name
        self.url = url
        self.path = path


class InvalidSectionError(cliapp.AppException):

    def __init__(self, repo, ref, section):
        Exception.__init__(self,
                           '%s:%s:.gitmodules: Found a misformatted section '
                           'title: [%s]' % (repo, ref, section))


class MissingSubmoduleCommitError(cliapp.AppException):

    def __init__(self, repo, ref, submodule):
        Exception.__init__(self,
                           '%s:%s:.gitmodules: No commit object found for '
                           'submodule "%s"' % (repo, ref, submodule))


class Submodules(object):

    def __init__(self, app, repo, ref):
        self.app = app
        self.repo = repo
        self.ref = ref
        self.submodules = []

    def load(self):
        content = self._read_gitmodules_file()

        io = StringIO.StringIO(content)
        parser = ConfigParser.RawConfigParser()
        parser.readfp(io)

        self._validate_and_read_entries(parser)

    def _read_gitmodules_file(self):
        try:
            # try to read the .gitmodules file from the repo/ref
            content = self.app.runcmd(
                    ['git', 'cat-file', 'blob', '%s:.gitmodules' % self.ref],
                    cwd=self.repo)

            # drop indentation in sections, as RawConfigParser cannot handle it
            return '\n'.join([line.strip() for line in content.splitlines()])
        except cliapp.AppException:
            raise NoModulesFileError(self.repo, self.ref)

    def _validate_and_read_entries(self, parser):
        for section in parser.sections():
            # validate section name against the 'section "foo"' pattern
            section_pattern = r'submodule "(.*)"'
            if re.match(section_pattern, section):
                # parse the submodule name, URL and path
                name = re.sub(section_pattern, r'\1', section)
                url = parser.get(section, 'url')
                path = parser.get(section, 'path')

                # create a submodule object
                submodule = Submodule(name, url, path)
                try:
                    # list objects in the parent repo tree to find the commit
                    # object that corresponds to the submodule
                    commit = self.app.runcmd(['git', 'ls-tree', self.ref,
                                              submodule.name], cwd=self.repo)

                    # read the commit hash from the output
                    fields = commit.split()
                    if len(fields) >= 2 and fields[1] == 'commit':
                        submodule.commit = commit.split()[2]

                        # fail if the commit hash is invalid
                        if len(submodule.commit) != 40:
                            raise MissingSubmoduleCommitError(self.repo,
                                                              self.ref,
                                                              submodule.name)

                        # add a submodule object to the list
                        self.submodules.append(submodule)
                    else:
                        logging.warning('Skipping submodule "%s" as %s:%s has '
                                 'a non-commit object for it' %
                                 (submodule.name, self.repo, self.ref))
                except cliapp.AppException:
                    raise MissingSubmoduleCommitError(self.repo, self.ref,
                                                      submodule.name)
            else:
                raise InvalidSectionError(self.repo, self.ref, section)

    def __iter__(self):
        for submodule in self.submodules:
            yield submodule

    def __len__(self):
        return len(self.submodules)


def set_remote(runcmd, gitdir, name, url):
    '''Set remote with name 'name' use a given url at gitdir'''
    return runcmd(['git', 'remote', 'set-url', name, url], cwd=gitdir)

def copy_repository(runcmd, repo, destdir):
    '''Copies a cached repository into a directory using cp.'''
    return runcmd(['cp', '-a', os.path.join(repo, '.git'), destdir])

def checkout_ref(runcmd, gitdir, ref):
    '''Checks out a specific ref/SHA1 in a git working tree.'''
    runcmd(['git', 'checkout', ref], cwd=gitdir)

def reset_workdir(runcmd, gitdir):
    '''Removes any differences between the current commit '''
    '''and the status of the working directory'''
    runcmd(['git', 'clean', '-fxd'], cwd=gitdir)
    runcmd(['git', 'reset', '--hard', 'HEAD'], cwd=gitdir)
