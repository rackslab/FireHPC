# Copyright (c) 2025 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path
import tempfile

import yaml

from firehpc.state import UserState, ClusterState
from firehpc.settings import ClusterSettings, ClusterRacksDBSettings
from firehpc.errors import FireHPCRuntimeError


class TestUserState(unittest.TestCase):
    def test_create(self):
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = UserState(tmp)
            self.assertFalse(state.path.exists())
            self.assertFalse(state.clusters.exists())
            state.create()
            self.assertTrue(state.path.exists())
            self.assertTrue(state.clusters.exists())


class TestClusterState(unittest.TestCase):
    def test_properties(self):
        state = ClusterState(UserState(Path("/tmp")), "foo")
        self.assertEqual(str(state.path), "/tmp/clusters/foo")
        self.assertEqual(str(state.conf), "/tmp/clusters/foo/conf")
        self.assertEqual(str(state.settings), "/tmp/clusters/foo/settings.yml")
        self.assertEqual(str(state.extravars), "/tmp/clusters/foo/conf/custom.yml")

    def test_create(self):
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(UserState(tmp), "foo")
            self.assertFalse(state.user_state.path.exists())
            self.assertFalse(state.user_state.clusters.exists())
            self.assertFalse(state.path.exists())
            self.assertFalse(state.exists())
            state.create()
            self.assertTrue(state.user_state.path.exists())
            self.assertTrue(state.user_state.clusters.exists())
            self.assertTrue(state.path.exists())
            self.assertTrue(state.exists())

    def test_clean(self):
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(UserState(tmp), "foo")
            state.create()
            state.clean()
            self.assertTrue(state.user_state.path.exists())
            self.assertTrue(state.user_state.clusters.exists())
            self.assertFalse(state.path.exists())
            self.assertFalse(state.exists())

    def test_conf_create(self):
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(UserState(tmp), "foo")
            state.create()
            self.assertFalse(state.conf.exists())
            state.conf_create()
            self.assertTrue(state.conf.exists())

    def test_conf_clean(self):
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(UserState(tmp), "foo")
            state.create()
            state.conf_create()
            state.conf_clean()
            self.assertFalse(state.conf.exists())

    def test_save(self):
        settings = ClusterSettings(
            os="debian12",
            environment="ansible-latest",
            slurm_emulator=False,
            racksdb=ClusterRacksDBSettings(db="path/to/db", schema="path/to/schema"),
            custom="path/to/custom",
        )
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(UserState(tmp), "foo")
            state.create()
            self.assertFalse(state.settings.exists())
            state.save(settings)
            self.assertTrue(state.settings.exists())

    def test_load(self):
        settings = ClusterSettings(
            os="debian12",
            environment="ansible-latest",
            slurm_emulator=False,
            racksdb=ClusterRacksDBSettings(db="path/to/db", schema="path/to/schema"),
            custom="path/to/custom",
        )
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(UserState(tmp), "foo")
            state.create()
            self.assertFalse(state.settings.exists())
            state.save(settings)
            settings = state.load()
            self.assertIsInstance(settings, ClusterSettings)

    def test_load_not_found(self):
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(UserState(tmp), "foo")
            state.create()
            self.assertFalse(state.settings.exists())
            with self.assertRaisesRegex(
                FireHPCRuntimeError,
                "^Unable to find cluster settings file .*/settings.yml$",
            ):
                state.load()

    def test_load_missing_parameter(self):
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            tmp.rmdir()
            state = ClusterState(UserState(tmp), "foo")
            state.create()
            self.assertFalse(state.settings.exists())
            with open(state.settings, "w+") as fh:
                fh.write(yaml.dump({"fail": True}))
            with self.assertRaisesRegex(
                FireHPCRuntimeError,
                "^Unable to load cluster settings: '.*'$",
            ):
                state.load()
