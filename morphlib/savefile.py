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


import logging
import os
import tempfile


class SaveFile(file):

    '''Save files with a temporary name and rename when they're ready.

    This class acts exactly like the normal ``file`` class, except that
    it is meant only for saving data to files. The data is written to
    a temporary file, which gets renamed to the target name when the
    open file is closed. This avoids readers of the file from getting
    an incomplete file.

    Example:

        f = SaveFile('foo', 'w')
        f.write(stuff)
        f.close()

    The file will be called something like ``tmpCAFEBEEF`` until ``close``
    is called, at which point it gets renamed to ``foo``.

    If the writer decides the file is not worth saving, they can call the
    ``abort`` method, which deletes the temporary file.

    '''

    def __init__(self, filename, *args, **kwargs):
        self.real_filename = filename
        dirname = os.path.dirname(filename)
        fd, self._savefile_tempname = tempfile.mkstemp(dir=dirname)
        os.close(fd)
        file.__init__(self, self._savefile_tempname, *args, **kwargs)

    def abort(self):
        '''Abort file saving.

        The temporary file will be removed, and the universe is almost
        exactly as if the file save had never started.

        '''

        os.remove(self._savefile_tempname)
        return file.close(self)

    def close(self):
        ret = file.close(self)
        logging.debug('Rename temporary file %s to %s' %
                      (self._savefile_tempname, self.real_filename))
        os.rename(self._savefile_tempname, self.real_filename)
        return ret
