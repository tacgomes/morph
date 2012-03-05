#!/bin/bash
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

set -ex

usage()
{
    cat 1>&2 <<EOF
Make a system image called DEST filled with the contents of TARBALL...
usage: $0 DEST TARBALL...
EOF
}


dummy_kpartx_add() 
{
    local img="$1"

    local start=$(sfdisk -d "$img" | 
                  awk '
                      $3 == "start=" && $4 != "0," {
                          gsub(/,/, "", $4)
                          print $4 * 512
                      }
                  ')

    losetup -o "$start" -f "$img"
    local device=""
    while true
    do
        device=$(losetup -j "$img" | sed 's,^\(/dev/loop[^:]*\):.*,\1,')
        if [ "x$device" != x ]
        then
            break
        fi
    done
    echo "$device"
}


dummy_kpartx_delete()
{
    losetup -j "$1" | 
    sed 's,^\(/dev/loop[^:]*\):.*,\1,' |
    while read device
    do
        losetup -d "$device"
    done
}


if [ "$#" -le 1 ]; then
    usage
    exit 1
fi

img="$1"
shift

# Create an empty file (a hole) as the raw disk image file.
dd if=/dev/zero of="$img" bs=16G seek=1 count=0

# Partition. See the sfdisk(8) manpage for an explanation of the input.
sfdisk "$img" <<EOF
1,,83,*
EOF

# Access the partition inside the raw disk image file.
part=$(dummy_kpartx_add "$img")
trap "dummy_kpartx_delete $img" EXIT

# Create filesystem. Note that for some reason sfdisk and mkfs when used
# on the loop device from dummy_kpartx_add get the image size wrong by
# about one block, which makes things break. So we force a filesystem
# size that fits (even if it doesn't quite fill the image).
mkfs -t ext4 -q "$part" 4194304

# Mount the filesystem.
mp="$(mktemp -d)"
mount "$part" "$mp"
trap "umount $part; dummy_kpartx_delete $img" EXIT

# Unpack all the strata that are to be installed.
for stratum
do
    tar -C "$mp" -xf "$stratum"
done

# Configure fstab for the new system.
cat <<EOF > "$mp/etc/fstab"
/dev/sda1 /        ext4   errors=remount-ro 0 1
EOF

# Install extlinux as the bootloader.
cat <<EOF > "$mp/extlinux.conf"
default linux
timeout 1

label linux
kernel /boot/vmlinuz
append root=/dev/sda1 init=/sbin/init rw
EOF

extlinux --install "$mp"
sync
sleep 2

