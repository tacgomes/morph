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

dd if=/dev/zero of="$img" bs=16G seek=1 count=0
parted -s "$img" mklabel msdos
parted -s "$img" mkpart primary 0% 100%
parted -s "$img" set 1 boot on
install-mbr "$img"


part=$(dummy_kpartx_add "$img")
trap "dummy_kpartx_delete $img" EXIT

# mapper may not yet be ready
while test ! -e "$part"; do :; done

mkfs -t ext4 -q "$part"

mp="$(mktemp -d)"
mount "$part" "$mp"
trap "umount $part; dummy_kpartx_delete $img" EXIT

for stratum
do
    tar -C "$mp" -xf "$stratum"
done

cat <<EOF | tee "$mp/etc/fstab" > /dev/null
/dev/sda1 /        ext4   errors=remount-ro 0 1
EOF

cat <<EOF | tee "$mp/extlinux.conf" > /dev/null
default linux
timeout 1

label linux
kernel /boot/vmlinuz
append root=/dev/sda1 init=/sbin/init rw
EOF

sudo extlinux --install "$mp"
sync
sleep 2

