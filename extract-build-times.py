#!/usr/bin/env python
#
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


import cliapp
import glob
import json
import os
import re
import StringIO


class ExtractBuildTimes(cliapp.Application):

    '''Extracts build times of chunks in a morph cache directory.

    Given a morph cache directory as the first argument, this app finds all
    cached chunks, loads their meta data and prints their build times.

    '''

    def process_args(self, args):
        cachedir = args[0]

        def chunk_hash(chunk):
            short = re.split('\.', chunk)
            return os.path.basename(short[-3])

        def chunk_name(chunk):
            short = re.split('\.', chunk)
            return short[-1]

        chunks = glob.glob(os.path.join(cachedir, '*.chunk.*'))
        items = []

        for chunk in chunks:
            hash = chunk_hash(chunk)
            metafile = os.path.join(cachedir, '%s.meta' % hash)
            with open(metafile) as f:
                data = f.read()
                io = StringIO.StringIO(data)
                metainfo = json.load(io)
                time = metainfo['build-times']['overall-build']['delta']
                minutes = float(time) / 60.0
                items.append((chunk_name(chunk), minutes))

        items = sorted(items, key=lambda x: x[1], reverse=True)

        for name, time in items:
            print '%30s: %3.0f mins' % (name, time)


if __name__ == '__main__':
    ExtractBuildTimes().run()
