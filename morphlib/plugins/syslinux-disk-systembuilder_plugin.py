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
import shutil
import time

import cliapp

import morphlib
from morphlib.builder2 import DiskImageBuilder


class SyslinuxDiskBuilder(DiskImageBuilder):  # pragma: no cover

    system_kind = 'syslinux-disk'

    def _install_mbr(self, arch, image_name):
        self.app.status(msg='Installing syslinux mbr on disk image %(fname)s',
                        fname=image_name, chatty=True)
        if arch not in ('x86', 'x86_64'):
            return
        with self.build_watch('install-mbr'):
            mbr_installed = False
            for path in self.app.settings['syslinux-mbr-search-paths']:
                if os.path.exists(path):
                    self.app.runcmd(['dd', 'if=' + path, 'of=' + image_name,
                                     'conv=notrunc'])
                    mbr_installed = True
                    break
            # A flag, rather than an else statement is used, since it must
            # fail if the search path is empty as well
            if not mbr_installed:
                raise morphlib.Error(
                    "No syslinux mbr found in search paths: %s" %
                    repr(self.app.settings['syslinux-mbr-search-paths']))

    def _create_bootloader_config(self, path):
        self.app.status(msg='Creating extlinux.conf in %(path)s',
                        path=path, chatty=True)
        with self.build_watch('create-extlinux-config'):
            config = os.path.join(path, 'extlinux.conf')
            with open(config, 'w') as f:
                f.write('default linux\n')
                f.write('timeout 1\n')
                f.write('label linux\n')
                f.write('kernel /boot/vmlinuz\n')
                f.write('append root=/dev/sda1 rootflags=subvol=factory-run '
                        'init=/sbin/init rw\n')

    def _install_boot_files(self, arch, sourcefs, targetfs):
        with self.build_watch('install-boot-files-extlinux'):
            if arch in ('x86', 'x86_64'):
                self.app.status(msg='Installing extlinux.conf', chatty=True)
                shutil.copy2(os.path.join(sourcefs, 'extlinux.conf'),
                             os.path.join(targetfs, 'extlinux.conf'))

        super(SyslinuxDiskBuilder, self)._install_boot_files(arch, sourcefs,
                                                             targetfs)

    def _install_bootloader(self, path):
        self.app.status(msg='Installing extlinux to %(path)s',
                        path=path, chatty=True)
        with self.build_watch('install-bootloader'):
            self.app.runcmd(['extlinux', '--install', path])

            # FIXME this hack seems to be necessary to let extlinux finish
            self.app.runcmd(['sync'])
            time.sleep(2)

class SyslinuxDiskBuilderPlugin(cliapp.Plugin):

    def enable(self):
        # Only provide this system builder on architectures that are
        # supported by syslinux.
        if morphlib.util.arch() in ['x86_64', 'i386', 'i486', 'i586', 'i686']:
            self.app.settings.string_list(
                ['syslinux-mbr-search-paths'],
                'A list of files to search for to use as the syslinux mbr',
                default=['/usr/lib/extlinux/mbr.bin',
                         '/usr/share/syslinux/mbr.bin'])
            self.app.system_kind_builder_factory.register(SyslinuxDiskBuilder)

    def disable(self):
        pass
