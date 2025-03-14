# Copyright (c) 2025 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path
import tempfile

from firehpc.state import ClusterState
from firehpc.settings import ClusterSettings


class TestClusterState(unittest.TestCase):

    def test_properties(self):
        state = ClusterState(Path("/tmp"), "foo")
        self.assertEqual(str(state.path), "/tmp/foo")
        self.assertEqual(str(state.conf), "/tmp/foo/conf")
        self.assertEqual(str(state.settings), "/tmp/foo/settings.yml")
        self.assertEqual(str(state.extravars), "/tmp/foo/conf/custom.yml")

    def test_create(self):
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(tmp, "foo")
            self.assertFalse(state.state.exists())
            self.assertFalse(state.path.exists())
            self.assertFalse(state.exists())
            state.create()
            self.assertTrue(state.state.exists())
            self.assertTrue(state.path.exists())
            self.assertTrue(state.exists())

    def test_clean(self):
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(tmp, "foo")
            state.create()
            state.clean()
            self.assertTrue(state.state.exists())
            self.assertFalse(state.path.exists())
            self.assertFalse(state.exists())

    def test_conf_create(self):
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(tmp, "foo")
            state.create()
            self.assertFalse(state.conf.exists())
            state.conf_create()
            self.assertTrue(state.conf.exists())

    def test_conf_clean(self):
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(tmp, "foo")
            state.create()
            state.conf_create()
            state.conf_clean()
            self.assertFalse(state.conf.exists())

    def test_save(self):
        settings = ClusterSettings()
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(tmp, "foo")
            state.create()
            self.assertFalse(state.settings.exists())
            state.save(settings)
            self.assertTrue(state.settings.exists())

    def test_load(self):
        settings = ClusterSettings()
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(tmp, "foo")
            state.create()
            self.assertFalse(state.settings.exists())
            state.save(settings)
            settings = state.load()
            self.assertIsInstance(settings, ClusterSettings)
