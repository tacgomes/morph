# Copyright (C) 2012-2015  Codethink Limited
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


def mount(runcmd, partition, mount_point, fstype=None): # pragma: no cover
    if not os.path.exists(mount_point):
        os.mkdir(mount_point)
    if not fstype:
        fstype = []
    else:
        fstype = ['-t', fstype]
    runcmd(['mount', partition, mount_point] + fstype)


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

    def normpath(path):
        if path == '.':
            return path
        path = os.path.normpath(path)
        if not os.path.isabs(path):
            path = os.path.join('.', path)
        return path
    def any_paths_are_subpath_of(prefix):
        prefix = normpath(prefix)
        norm_paths = (normpath(path) for path in paths)
        return any(path[:len(prefix)] == prefix
                   for path in norm_paths)

    def path_is_listed(path):
        return any(normpath(path) == normpath(other)
                   for other in paths)

    for dirpath, dirnames, filenames in tree_walker:

        if path_is_listed(dirpath):
            # No subpaths need to be considered
            del dirnames[:]
            del filenames[:]
        elif any_paths_are_subpath_of(dirpath):
            # Subpaths may be marked, or may not, need to leave this
            # writable, so don't yield, but we don't cull.
            pass
        else:
            # not listed as a parent or an exact match, needs to be
            # yielded, but we don't need to consider subdirs, so can cull
            yield dirpath
            del dirnames[:]
            del filenames[:]

        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)
            if path_is_listed(fullpath):
                pass
            else:
                yield fullpath
