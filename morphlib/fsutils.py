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

import os
import re


def create_image(runcmd, image_name, size):
    # FIXME a pure python implementation may be better
    runcmd(['dd', 'if=/dev/zero', 'of=' + image_name, 'bs=1',
            'seek=%d' % size, 'count=0'])

def partition_image(runcmd, image_name):
    # FIXME make this more flexible with partitioning options
    runcmd(['sfdisk', image_name], feed_stdin='1,,83,*\n')

def install_mbr(runcmd, image_name):
    for path in ['/usr/lib/extlinux/mbr.bin',
                 '/usr/share/syslinux/mbr.bin']:
        if os.path.exists(path):
            runcmd(['dd', 'if=' + path, 'of=' + image_name,
                    'conv=notrunc'])
            break

def setup_device_mapping(runcmd, image_name):
    findstart = re.compile(r"start=\s+(\d+),")
    out = runcmd(['sfdisk', '-d', image_name])
    for line in out.splitlines():
        match = findstart.search(line)
        if match is None:
            continue
        start = int(match.group(1)) * 512
        if start != 0:
            break
    
    runcmd(['losetup', '-o', str(start), '-f', image_name])
    
    out = runcmd(['losetup', '-j', image_name])
    line = out.strip()
    i = line.find(':')
    return line[:i]

def create_fs(runcmd, partition):
    # FIXME: the hardcoded size of 4GB is icky but the default broke
    # when we used mkfs -t ext4
    runcmd(['mkfs.btrfs', '-L', 'baserock',
            '-b', '4294967296', partition])

def mount(runcmd, partition, mount_point):
    if not os.path.exists(mount_point):
        os.mkdir(mount_point)
    runcmd(['mount', partition, mount_point])

def unmount(runcmd, mount_point):
    runcmd(['umount', mount_point])

def undo_device_mapping(runcmd, image_name):
    out = runcmd(['losetup', '-j', image_name])
    for line in out.splitlines():
        i = line.find(':')
        device = line[:i]
        runcmd(['losetup', '-d', device])
