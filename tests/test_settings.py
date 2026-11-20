# Copyright (c) 2025 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import argparse
import os
import copy
import tempfile
from unittest import mock
from pathlib import Path

from firehpc.settings import (
    ClusterSettings,
    ClusterRacksDBSettings,
    UserPreferences,
    REMOTE_ENV_VAR,
    default_preferences_path,
    explicit_remote,
    resolve_remote,
)


BASE_SETTINGS = {
    "os": "debian12",
    "environment": "ansible-latest",
    "slurm_emulator": False,
}


class TestClusterSettings(unittest.TestCase):
    def test_init(self):
        settings = ClusterSettings(
            os="debian12",
            environment="ansible-latest",
            slurm_emulator=False,
            racksdb=ClusterRacksDBSettings(),
        )
        self.assertEqual(settings.os, "debian12")
        self.assertEqual(settings.environment, "ansible-latest")
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
        settings = ClusterSettings.from_values(
            os="debian12",
            environment="ansible-latest",
            slurm_emulator=args.slurm_emulator,
            db=args.db,
            schema=args.schema,
            custom=args.custom,
        )
        self.assertEqual(settings.os, "debian12")
        self.assertEqual(settings.environment, "ansible-latest")
        self.assertIsNone(settings.racksdb.db)
        self.assertIsNone(settings.racksdb.schema)
        self.assertFalse(settings.slurm_emulator)
        self.assertIsNone(settings.custom)
        self.assertSerializing(settings)

    def test_args_custom(self):
        args = self.parse_args(["--custom", "/tmp/custom"])
        settings = ClusterSettings.from_values(
            os="debian12",
            environment="ansible-latest",
            slurm_emulator=args.slurm_emulator,
            db=args.db,
            schema=args.schema,
            custom=args.custom,
        )
        self.assertEqual(settings.os, "debian12")
        self.assertEqual(settings.environment, "ansible-latest")
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
        settings = ClusterSettings.from_values(
            os="debian12",
            environment="ansible-latest",
            slurm_emulator=args.slurm_emulator,
            db=args.db,
            schema=args.schema,
            custom=args.custom,
        )
        os.chdir(cwd)

        self.assertEqual(settings.os, "debian12")
        self.assertEqual(settings.environment, "ansible-latest")
        self.assertIsNone(settings.racksdb.db)
        self.assertIsNone(settings.racksdb.schema)
        self.assertFalse(settings.slurm_emulator)
        self.assertIsInstance(settings.custom, Path)
        self.assertEqual(str(settings.custom), "/tmp/custom")
        self.assertSerializing(settings)

    def test_args_racksdb(self):
        args = self.parse_args(["--db", "/tmp/db", "--schema", "/tmp/schema"])
        settings = ClusterSettings.from_values(
            os="debian12",
            environment="ansible-latest",
            slurm_emulator=args.slurm_emulator,
            db=args.db,
            schema=args.schema,
            custom=args.custom,
        )
        self.assertEqual(settings.os, "debian12")
        self.assertEqual(settings.environment, "ansible-latest")
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
        settings = ClusterSettings.from_values(
            os="debian12",
            environment="ansible-latest",
            slurm_emulator=args.slurm_emulator,
            db=args.db,
            schema=args.schema,
            custom=args.custom,
        )
        os.chdir(cwd)

        self.assertEqual(settings.os, "debian12")
        self.assertEqual(settings.environment, "ansible-latest")
        self.assertIsInstance(settings.racksdb.db, Path)
        self.assertEqual(str(settings.racksdb.db), "/tmp/db")
        self.assertIsInstance(settings.racksdb.schema, Path)
        self.assertEqual(str(settings.racksdb.schema), "/tmp/schema")
        self.assertFalse(settings.slurm_emulator)
        self.assertIsNone(settings.custom)
        self.assertSerializing(settings)

    def test_args_slurm_emulator(self):
        args = self.parse_args(["--slurm-emulator"])
        settings = ClusterSettings.from_values(
            os="debian12",
            environment="ansible-latest",
            slurm_emulator=args.slurm_emulator,
            db=args.db,
            schema=args.schema,
            custom=args.custom,
        )
        self.assertEqual(settings.os, "debian12")
        self.assertEqual(settings.environment, "ansible-latest")
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
        self.assertEqual(settings.os, "debian12")
        self.assertEqual(settings.environment, "ansible-latest")
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
        self.assertEqual(settings.os, "debian12")
        self.assertEqual(settings.environment, "ansible-latest")
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
        self.assertEqual(settings.os, "debian12")
        self.assertEqual(settings.environment, "ansible-latest")
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
        self.assertEqual(settings.os, "debian12")
        self.assertEqual(settings.environment, "ansible-latest")
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
        self.assertEqual(settings.os, "debian12")
        self.assertEqual(settings.environment, "ansible-latest")
        self.assertIsNone(settings.racksdb.db)
        self.assertIsNone(settings.racksdb.schema)
        self.assertIsNone(settings.custom)


class TestClusterSettingsRemote(unittest.TestCase):
    def test_default_local(self):
        settings = ClusterSettings.deserialize(copy.deepcopy(BASE_SETTINGS))
        self.assertIsNone(settings.remote)
        self.assertNotIn("remote", settings.serialize())

    def test_serialize_remote(self):
        settings = ClusterSettings.from_values(
            os="debian12",
            environment="ansible-latest",
            slurm_emulator=False,
            remote="user@server",
        )
        self.assertEqual(settings.serialize()["remote"], "user@server")
        copy_ = ClusterSettings.deserialize(settings.serialize())
        self.assertEqual(copy_.remote, "user@server")

    def test_empty_remote(self):
        settings = ClusterSettings.from_values(
            os="debian12",
            environment="ansible-latest",
            slurm_emulator=False,
            remote="",
        )
        self.assertIsNone(settings.remote)


class TestUserPreferences(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "firehpc" / "firehpc.ini"

    def tearDown(self):
        self.tmpdir.cleanup()

    def write(self, content):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content)

    def test_default_path_xdg(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.tmpdir.name}):
            self.assertEqual(default_preferences_path(), self.path)

    def test_missing_file(self):
        preferences = UserPreferences(self.path)
        self.assertIsNone(preferences.remote_host)
        self.assertEqual(preferences.remote_agent, "firehpc-agent")

    def test_remote(self):
        self.write("[remote]\nhost = user@server\nagent = /opt/bin/firehpc-agent\n")
        preferences = UserPreferences(self.path)
        self.assertEqual(preferences.remote_host, "user@server")
        self.assertEqual(preferences.remote_agent, "/opt/bin/firehpc-agent")

    def test_empty_host(self):
        self.write("[remote]\nhost =\n")
        self.assertIsNone(UserPreferences(self.path).remote_host)


class TestResolveRemote(unittest.TestCase):
    def setUp(self):
        self.preferences = mock.Mock(remote_host="prefs")

    def args(self, remote=None, local=False):
        return argparse.Namespace(remote=remote, local=local)

    def test_preferences(self):
        with mock.patch.dict(os.environ, clear=True):
            self.assertIsNone(explicit_remote(self.args()))
            self.assertEqual(resolve_remote(self.args(), self.preferences), "prefs")

    def test_env_over_preferences(self):
        with mock.patch.dict(os.environ, {REMOTE_ENV_VAR: "env"}, clear=True):
            self.assertEqual(explicit_remote(self.args()), "env")
            self.assertEqual(resolve_remote(self.args(), self.preferences), "env")

    def test_args_over_env(self):
        with mock.patch.dict(os.environ, {REMOTE_ENV_VAR: "env"}, clear=True):
            self.assertEqual(
                resolve_remote(self.args(remote="cli"), self.preferences), "cli"
            )

    def test_local(self):
        with mock.patch.dict(os.environ, {REMOTE_ENV_VAR: "env"}, clear=True):
            self.assertEqual(explicit_remote(self.args(local=True)), "")
            self.assertIsNone(resolve_remote(self.args(local=True), self.preferences))

    def test_nothing(self):
        self.preferences.remote_host = None
        with mock.patch.dict(os.environ, clear=True):
            self.assertIsNone(resolve_remote(self.args(), self.preferences))
