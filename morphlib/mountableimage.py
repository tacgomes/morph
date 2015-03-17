# Copyright (C) 2012-2013,2015  Codethink Limited
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
# with this program.  If not, see <http://www.gnu.org/licenses/>.


import cliapp
import logging
import os
import tempfile
import gzip

import morphlib


class MountableImage(object): # pragma: no cover

    '''Mountable image (deals with decompression).

    Note, this is a read-only mount in the sense that the decompressed
    image is not then recompressed after, instead any changes are discarded.

    '''
    def __init__(self, app, artifact_path):
        self.app = app
        self.artifact_path = artifact_path

    def setup(self, path):
        self.app.status(msg='Preparing image %(path)s', path=path, chatty=True)
        self.app.status(msg='  Decompressing...', chatty=True)
        (tempfd, self.temp_path) = \
            tempfile.mkstemp(dir=self.app.settings['tempdir'])

        try:
            with os.fdopen(tempfd, "wb") as outfh:
                infh = gzip.open(path, "rb")
                morphlib.util.copyfileobj(infh, outfh)
                infh.close()
        except BaseException as e:
            logging.error('Caught exception: %s' % str(e))
            logging.info('Removing temporary file %s' % self.temp_path)
            os.unlink(self.temp_path)
            raise
        self.app.status(msg='  Mounting image at %(path)s',
                        path=self.temp_path, chatty=True)
        part = morphlib.fsutils.setup_device_mapping(self.app.runcmd,
                                                     self.temp_path)
        mount_point = tempfile.mkdtemp(dir=self.app.settings['tempdir'])
        morphlib.fsutils.mount(self.app.runcmd, part, mount_point)
        self.mount_point = mount_point
        return mount_point

    def cleanup(self, path, mount_point):
        self.app.status(msg='Clearing down image at %(path)s', path=path,
                        chatty=True)
        try:
            morphlib.fsutils.unmount(self.app.runcmd, mount_point)
        except BaseException as e:
            logging.info('Ignoring error when unmounting: %s' % str(e))
        try:
            morphlib.fsutils.undo_device_mapping(self.app.runcmd, path)
        except BaseException as e:
            logging.info(
                'Ignoring error when undoing device mapping: %s' % str(e))
        try:
            os.rmdir(mount_point)
            os.unlink(path)
        except BaseException as e:
            logging.info(
                'Ignoring error when removing temporary files: %s' % str(e))

    def __enter__(self):
        return self.setup(self.artifact_path)

    def __exit__(self, exctype, excvalue, exctraceback):
        self.cleanup(self.temp_path, self.mount_point)
