# Copyright (C) 2011-2013  Codethink Limited
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


'''Baserock library.'''


import cliapp

import gitversion

__version__ = gitversion.version


class Error(cliapp.AppException):

    '''Base for all morph exceptions that cause user-visible messages.'''


import artifact
import artifactcachereference
import artifactresolver
import bins
import buildcommand
import buildenvironment
import buildorder
import buildsystem
import builder2
import cachedir
import cachedrepo
import cachekeycomputer
import fsutils
import git
import localartifactcache
import localrepocache
import morph2
import morphologyfactory
import remoteartifactcache
import remoterepocache
import repoaliasresolver
import savefile
import source
import sourcepool
import stagingarea
import stopwatch
import tempdir
import util
import yamlparse

import app  # this needs to be last
