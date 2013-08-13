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

import os
import re


def create_image(runcmd, image_name, size): # pragma: no cover
    # FIXME a pure python implementation may be better
    runcmd(['dd', 'if=/dev/zero', 'of=' + image_name, 'bs=1',
            'seek=%d' % size, 'count=0'])


def partition_image(runcmd, image_name): # pragma: no cover
    # FIXME make this more flexible with partitioning options
    runcmd(['sfdisk', image_name], feed_stdin='1,,83,*\n')


def setup_device_mapping(runcmd, image_name): # pragma: no cover
    findstart = re.compile(r"start=\s+(\d+),")
    out = runcmd(['sfdisk', '-d', image_name])
    for line in out.splitlines():
        match = findstart.search(line)
        if match is None:
            continue
        start = int(match.group(1)) * 512
        if start != 0:
            break

    device = runcmd(['losetup', '--show', '-o', str(start), '-f', image_name])
    return device.strip()


def create_fs(runcmd, partition): # pragma: no cover
    runcmd(['mkfs.btrfs', '-L', 'baserock', partition])


def mount(runcmd, partition, mount_point): # pragma: no cover
    if not os.path.exists(mount_point):
        os.mkdir(mount_point)
    runcmd(['mount', partition, mount_point])


def unmount(runcmd, mount_point): # pragma: no cover
    runcmd(['umount', mount_point])


def undo_device_mapping(runcmd, image_name): # pragma: no cover
    out = runcmd(['losetup', '-j', image_name])
    for line in out.splitlines():
        i = line.find(':')
        device = line[:i]
        runcmd(['losetup', '-d', device])


def invert_paths(tree_walker, paths):
    '''List paths from `tree_walker` that are not in `paths`.

    Given a traversal of a tree and a set of paths separated by os.sep,
    return the files and directories that are not part of the set of
    paths, culling directories that do not need to be recursed into,
    if the traversal supports this.

    `tree_walker` is expected to follow similar behaviour to `os.walk()`.

    This function will remove directores from the ones listed, to avoid
    traversing into these subdirectories, if it doesn't need to.

    As such, if a directory is returned, it is implied that its contents
    are also not in the set of paths.

    If the tree walker does not support culling the traversal this way,
    such as `os.walk(root, topdown=False)`, then the contents will also
    be returned.

    The purpose for this is to list the directories that can be made
    read-only, such that it would leave everything in paths writable.

    Each path in `paths` is expected to begin with the same path as
    yielded by the tree walker.

    '''

    def is_subpath(prefix, path):
        prefix_components = prefix.split(os.sep)
        path_components = path.split(os.sep)
        return path_components[:len(prefix_components)] == prefix_components

    for dirpath, dirnames, filenames in tree_walker:

        dn_copy = list(dirnames)
        for subdir in dn_copy:
            subdirpath = os.path.join(dirpath, subdir)
            for p in paths:
                # Subdir is an exact match for a given path
                # Don't recurse into it, so remove from list
                # Also don't yield it as we're inverting
                if subdirpath == p:
                    dirnames.remove(subdir)
                    break
                # This directory is a parent directory of one
                # of our paths, recurse into it, but don't yield it
                elif is_subpath(subdirpath, p):
                    break
            else:
                dirnames.remove(subdir)
                yield subdirpath

        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)
            for p in paths:
                # The file path is a child of one of the paths
                # or is equal. Don't yield because either it is
                # one of the specified paths, or is a file in a
                # directory specified by a path
                if is_subpath(p, fullpath):
                    break
            else:
                yield fullpath
