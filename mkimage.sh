#!/bin/bash
usage(){
cat >&2 <<EOF
Make a system image called DEST filled with the contents of TARBALL...
usage: $0 DEST TARBALL...
EOF
}

if [ "$#" -le 1 ]; then
    usage
    exit 1
fi

img="$1"
shift

sudo dd if=/dev/zero of="$img" bs=16G seek=1 count=0
sudo parted -s "$img" mklabel msdos
sudo parted -s "$img" mkpart primary 0% 100%
sudo parted -s "$img" set 1 boot on
sudo install-mbr "$img"
part=/dev/mapper/$(sudo kpartx -av "$img" | 
                   awk '/^add map/ { print $3 }' | 
                   head -n1)
trap "sudo kpartx -dv $img" EXIT
# mapper may not yet be ready
while test ! -e "$part"; do :; done
sudo mkfs -t ext4 "$part"
mp="$(mktemp -d)"
sudo mount "$part" "$mp"
trap "sudo umount $part; sudo kpartx -dv $img" EXIT

for stratum; do
    sudo tar -C "$mp" -xf "$stratum"
done

cat <<EOF | sudo tee "$mp/etc/fstab"
/dev/sda1 /        ext4   errors=remount-ro 0 1
EOF

cat <<EOF | sudo tee "$mp/extlinux.conf"
default linux
timeout 1

label linux
kernel /boot/vmlinuz
append root=/dev/sda1 init=/sbin/init quiet rw
EOF

sudo extlinux --install "$mp"
sync
sleep 2
