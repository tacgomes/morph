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


import cliapp
import os
import shutil
import tarfile
import tempfile
import unittest

import morphlib


class FakeBuildEnvironment(object):

    def __init__(self):
        self.env = {
        }
        self.extra_path = ['/extra-path']

class FakeSource(object):

    def __init__(self):
        self.morphology = {
            'name': 'le-name',
        }
        self.name = 'le-name'


class FakeApplication(object):

    def __init__(self, cachedir, tempdir):
        self.settings = {
            'cachedir': cachedir,
            'tempdir': tempdir,
        }
        for leaf in ('chunks',):
            d = os.path.join(tempdir, leaf)
            if not os.path.exists(d):
                os.makedirs(d)

    def runcmd(self, *args, **kwargs):
        return cliapp.runcmd(*args, **kwargs)

    def runcmd_unchecked(self, *args, **kwargs):
        return cliapp.runcmd_unchecked(*args, **kwargs)

    def status(self, **kwargs):
        pass


class StagingAreaTests(unittest.TestCase):

    def setUp(self):
        self.source = FakeSource()
        self.tempdir = tempfile.mkdtemp()
        self.cachedir = os.path.join(self.tempdir, 'cachedir')
        os.mkdir(self.cachedir)
        os.mkdir(os.path.join(self.cachedir, 'artifacts'))
        self.staging = os.path.join(self.tempdir, 'staging')
        self.created_dirs = []
        self.build_env = FakeBuildEnvironment()
        self.sa = morphlib.stagingarea.StagingArea(
            FakeApplication(self.cachedir, self.tempdir), self.source,
            self.staging, self.build_env)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def create_chunk(self):
        chunkdir = os.path.join(self.tempdir, 'chunk')
        os.mkdir(chunkdir)
        with open(os.path.join(chunkdir, 'file.txt'), 'w'):
            pass
        chunk_tar = os.path.join(self.tempdir, 'chunk.tar')
        tf = tarfile.TarFile(name=chunk_tar, mode='w')
        tf.add(chunkdir, arcname='.')
        tf.close()

        return chunk_tar

    def list_tree(self, root):
        files = []
        for dirname, subdirs, basenames in os.walk(root):
            paths = [os.path.join(dirname, x) for x in basenames]
            for x in [dirname] + paths:
                files.append(x[len(root):] or '/')
        return sorted(files)

    def test_remembers_specified_directory(self):
        self.assertEqual(self.sa.dirname, self.staging)

    def test_makes_relative_name(self):
        filename = 'foobar'
        self.assertEqual(self.sa.relative(filename), '/foobar')

    def test_installs_artifact(self):
        chunk_tar = self.create_chunk()
        with open(chunk_tar, 'rb') as f:
            self.sa.install_artifact(f)
        self.assertEqual(self.list_tree(self.staging),
                         sorted( ['/', '/file.txt',
                                  self.sa.relative_destdir(),
                                  self.sa.relative_builddir()]))

    def test_removes_everything(self):
        chunk_tar = self.create_chunk()
        with open(chunk_tar, 'rb') as f:
            self.sa.install_artifact(f)
        self.sa.remove()
        self.assertFalse(os.path.exists(self.staging))


class StagingAreaNonIsolatedTests(unittest.TestCase):

    def setUp(self):
        self.source = FakeSource()
        self.tempdir = tempfile.mkdtemp()
        self.staging = os.path.join(self.tempdir, 'staging')
        self.build_env = FakeBuildEnvironment()
        self.sa = morphlib.stagingarea.StagingArea(
            object(), self.source, self.staging, self.build_env,
            use_chroot=False)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_supports_non_isolated_mode(self):
        filename = os.path.join(self.staging, 'foobar')
        self.assertEqual(self.sa.relative(filename), filename)
