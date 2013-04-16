# Copyright (C) 2012-2013  Codethink Limited
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
import gzip
import logging
import os
import tempfile
import shutil

import morphlib


class ExtractedTarball(object): # pragma: no cover

    '''Tarball extracted in a temporary directory.

    This can be used e.g. to inspect the contents of a rootfs tarball.

    '''
    def __init__(self, app, tarball):
        self.app = app
        self.tarball = tarball

    def setup(self):
        self.app.status(msg='Preparing tarball %(tarball)s',
                        tarball=os.path.basename(self.tarball), chatty=True)
        self.app.status(msg='  Extracting...', chatty=True)
        self.tempdir = tempfile.mkdtemp(dir=self.app.settings['tempdir'])
        try:
            morphlib.bins.unpack_binary(self.tarball, self.tempdir)
        except BaseException, e:
            logging.error('Caught exception: %s' % str(e))
            logging.debug('Removing temporary directory %s' % self.tempdir)
            shutil.rmtree(self.tempdir)
            raise
        return self.tempdir

    def cleanup(self):
        self.app.status(msg='Cleanup extracted tarball %(tarball)s',
                        tarball=os.path.basename(self.tarball), chatty=True)
        try:
            shutil.rmtree(self.tempdir)
        except BaseException, e:
            logging.warning(
                'Error when removing temporary directory %s: %s' %
                    (self.tempdir, str(e)))

    def __enter__(self):
        return self.setup()

    def __exit__(self, exctype, excvalue, exctraceback):
        self.cleanup()
