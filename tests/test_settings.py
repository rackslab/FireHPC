# Copyright (c) 2025 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import argparse
import os
import copy
from pathlib import Path

from firehpc.settings import ClusterSettings, ClusterRacksDBSettings


BASE_SETTINGS = {
    "slurm_emulator": False,
}


class TestClusterSettings(unittest.TestCase):

    def test_init(self):
        settings = ClusterSettings()
        self.assertIsInstance(settings.racksdb, ClusterRacksDBSettings)
        self.assertIsNone(settings.racksdb.db)
        self.assertIsNone(settings.racksdb.schema)
        self.assertFalse(settings.slurm_emulator)
        self.assertIsNone(settings.custom)

    def parse_args(self, args):
        parser = argparse.ArgumentParser(description="Testing argument parser")
        parser.add_argument(
            "--db",
            help="Path to RacksDB database",
            type=Path,
        )
        parser.add_argument(
            "--schema",
            help="Path to RacksDB schema",
            type=Path,
        )
        parser.add_argument(
            "-c",
            "--custom",
            help="Path of variables directories to customize FireHPC default",
            type=Path,
        )
        parser.add_argument(
            "--slurm-emulator",
            help="Enable Slurm emulator mode",
            action="store_true",
        )
        return parser.parse_args(args)

    def assertSerializing(self, settings):
        copy = ClusterSettings.deserialize(settings.serialize())
        self.assertEqual(settings.racksdb.db, copy.racksdb.db)
        self.assertEqual(settings.racksdb.schema, copy.racksdb.schema)
        self.assertEqual(settings.slurm_emulator, copy.slurm_emulator)
        self.assertEqual(settings.custom, copy.custom)

    def test_args_empty(self):
        args = self.parse_args([])
        settings = ClusterSettings.from_args(args)
        self.assertIsNone(settings.racksdb.db)
        self.assertIsNone(settings.racksdb.schema)
        self.assertFalse(settings.slurm_emulator)
        self.assertIsNone(settings.custom)
        self.assertSerializing(settings)

    def test_args_custom(self):
        args = self.parse_args(["--custom", "/tmp/custom"])
        settings = ClusterSettings.from_args(args)
        self.assertIsNone(settings.racksdb.db)
        self.assertIsNone(settings.racksdb.schema)
        self.assertFalse(settings.slurm_emulator)
        self.assertIsInstance(settings.custom, Path)
        self.assertEqual(str(settings.custom), "/tmp/custom")
        self.assertSerializing(settings)

    def test_args_custom_relative(self):
        cwd = os.getcwd()
        os.chdir("/tmp")
        args = self.parse_args(["--custom", "custom"])
        settings = ClusterSettings.from_args(args)
        os.chdir(cwd)

        self.assertIsNone(settings.racksdb.db)
        self.assertIsNone(settings.racksdb.schema)
        self.assertFalse(settings.slurm_emulator)
        self.assertIsInstance(settings.custom, Path)
        self.assertEqual(str(settings.custom), "/tmp/custom")
        self.assertSerializing(settings)

    def test_args_racksdb(self):
        args = self.parse_args(["--db", "/tmp/db", "--schema", "/tmp/schema"])
        settings = ClusterSettings.from_args(args)
        self.assertIsInstance(settings.racksdb.db, Path)
        self.assertEqual(str(settings.racksdb.db), "/tmp/db")
        self.assertIsInstance(settings.racksdb.schema, Path)
        self.assertEqual(str(settings.racksdb.schema), "/tmp/schema")
        self.assertFalse(settings.slurm_emulator)
        self.assertIsNone(settings.custom)
        self.assertSerializing(settings)

    def test_args_racksdb_relative(self):
        cwd = os.getcwd()
        os.chdir("/tmp")
        args = self.parse_args(["--db", "db", "--schema", "schema"])
        settings = ClusterSettings.from_args(args)
        os.chdir(cwd)

        self.assertIsInstance(settings.racksdb.db, Path)
        self.assertEqual(str(settings.racksdb.db), "/tmp/db")
        self.assertIsInstance(settings.racksdb.schema, Path)
        self.assertEqual(str(settings.racksdb.schema), "/tmp/schema")
        self.assertFalse(settings.slurm_emulator)
        self.assertIsNone(settings.custom)
        self.assertSerializing(settings)

    def test_args_slurm_emulator(self):
        args = self.parse_args(["--slurm-emulator"])
        settings = ClusterSettings.from_args(args)
        self.assertIsNone(settings.racksdb.db)
        self.assertIsNone(settings.racksdb.schema)
        self.assertTrue(settings.slurm_emulator)
        self.assertIsNone(settings.custom)
        self.assertSerializing(settings)

    def test_update_args_custom(self):
        content = copy.deepcopy(BASE_SETTINGS)
        content["custom"] = "/tmp/initial"
        settings = ClusterSettings.deserialize(content)
        self.assertIsInstance(settings.custom, Path)
        self.assertEqual(str(settings.custom), "/tmp/initial")

        args = self.parse_args(["--custom", "/tmp/from-args"])
        settings.update_from_args(args)

        # Check value has changed for custom
        self.assertIsInstance(settings.custom, Path)
        self.assertEqual(str(settings.custom), "/tmp/from-args")

        # Check values did not change for other parameters
        self.assertIsNone(settings.racksdb.db)
        self.assertIsNone(settings.racksdb.schema)
        self.assertFalse(settings.slurm_emulator)

    def test_update_args_custom_relative(self):
        content = copy.deepcopy(BASE_SETTINGS)
        content["custom"] = "/tmp/initial"
        settings = ClusterSettings.deserialize(content)
        self.assertIsInstance(settings.custom, Path)
        self.assertEqual(str(settings.custom), "/tmp/initial")

        cwd = os.getcwd()
        os.chdir("/tmp")
        args = self.parse_args(["--custom", "from-args"])
        settings.update_from_args(args)
        os.chdir(cwd)

        # Check value has changed for custom
        self.assertIsInstance(settings.custom, Path)
        self.assertEqual(str(settings.custom), "/tmp/from-args")

        # Check values did not change for other parameters
        self.assertIsNone(settings.racksdb.db)
        self.assertIsNone(settings.racksdb.schema)
        self.assertFalse(settings.slurm_emulator)

    def test_update_args_racksdb(self):
        content = copy.deepcopy(BASE_SETTINGS)
        content["racksdb"] = {"db": "/tmp/initial"}
        settings = ClusterSettings.deserialize(content)
        self.assertIsInstance(settings.racksdb.db, Path)
        self.assertEqual(str(settings.racksdb.db), "/tmp/initial")
        self.assertIsNone(settings.racksdb.schema)

        args = self.parse_args(
            ["--db", "/tmp/from-args", "--schema", "/tmp/schema-from-args"]
        )
        settings.update_from_args(args)

        # Check value has changed for racksdb parameters
        self.assertIsInstance(settings.racksdb.db, Path)
        self.assertEqual(str(settings.racksdb.db), "/tmp/from-args")
        self.assertIsInstance(settings.racksdb.schema, Path)
        self.assertEqual(str(settings.racksdb.schema), "/tmp/schema-from-args")

        # Check values did not change for other parameters
        self.assertIsNone(settings.custom)
        self.assertFalse(settings.slurm_emulator)

    def test_update_args_racksdb_relative(self):
        content = copy.deepcopy(BASE_SETTINGS)
        content["racksdb"] = {
            "db": "/tmp/initial",
        }
        settings = ClusterSettings.deserialize(content)
        self.assertIsInstance(settings.racksdb.db, Path)
        self.assertEqual(str(settings.racksdb.db), "/tmp/initial")
        self.assertIsNone(settings.racksdb.schema)

        cwd = os.getcwd()
        os.chdir("/tmp")
        args = self.parse_args(["--db", "from-args", "--schema", "schema-from-args"])
        settings.update_from_args(args)
        os.chdir(cwd)

        # Check value has changed for racksdb parameters
        self.assertIsInstance(settings.racksdb.db, Path)
        self.assertEqual(str(settings.racksdb.db), "/tmp/from-args")
        self.assertIsInstance(settings.racksdb.schema, Path)
        self.assertEqual(str(settings.racksdb.schema), "/tmp/schema-from-args")

        # Check values did not change for other parameters
        self.assertIsNone(settings.custom)
        self.assertFalse(settings.slurm_emulator)

    def test_update_args_slurm_emulator(self):
        content = copy.deepcopy(BASE_SETTINGS)
        settings = ClusterSettings.deserialize(content)
        self.assertFalse(settings.slurm_emulator)

        args = self.parse_args(["--slurm-emulator"])
        settings.update_from_args(args)

        # Check value has changed for slurm emulator
        self.assertTrue(settings.slurm_emulator)

        # Check values did not change for other parameters
        self.assertIsNone(settings.racksdb.db)
        self.assertIsNone(settings.racksdb.schema)
        self.assertIsNone(settings.custom)
