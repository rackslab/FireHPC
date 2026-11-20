# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from firehpc.errors import FireHPCRuntimeError
from firehpc.exec import MIN_USERS, FireHPCExec
from firehpc.state import UserState


class TestArgs(unittest.TestCase):
    def parse_args(self, args):
        cli = FireHPCExec.__new__(FireHPCExec)
        return cli._parser().parse_args(args)

    def parse_deploy(self, args):
        return self.parse_args(
            ["deploy", "--os", "debian13", "--cluster", "hpc", *args]
        )

    def test_deploy_defaults(self):
        args = self.parse_deploy([])
        self.assertEqual(args.action, "deploy")
        self.assertEqual(args.users, 10)
        self.assertIsNone(args.users_from)

    def test_users_custom_count(self):
        args = self.parse_deploy(["--users", "20"])
        self.assertEqual(args.users, 20)

    def test_users_below_minimum(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.parse_deploy(["--users", str(MIN_USERS - 1)])

    def test_users_minimum_accepted(self):
        args = self.parse_deploy(["--users", str(MIN_USERS)])
        self.assertEqual(args.users, MIN_USERS)


class TestRemoteArgs(unittest.TestCase):
    def parse_args(self, args):
        cli = FireHPCExec.__new__(FireHPCExec)
        return cli._parser().parse_args(args)

    def test_remote_exec(self):
        args = self.parse_args(
            ["--remote", "server", "remote", "exec", "--", "machinectl", "--version"]
        )
        self.assertEqual(args.remote, "server")
        self.assertEqual(args.remote_action, "exec")
        self.assertEqual(args.cmd, ["--", "machinectl", "--version"])

    def test_remote_transfers(self):
        for action in ("upload", "download"):
            with self.subTest(action=action):
                args = self.parse_args(["remote", action, "/src", "/dst"])
                self.assertEqual(args.remote_action, action)
                self.assertEqual((args.source, args.destination), ("/src", "/dst"))

    def test_remote_hidden_from_help(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            self.parse_args(["--help"])
        self.assertNotIn("remote}", out.getvalue())
        self.assertNotIn(",remote", out.getvalue())


class TestDeployState(unittest.TestCase):
    """Errors before deployment must not leave a cluster state."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.cli = FireHPCExec.__new__(FireHPCExec)
        self.cli.args = self.cli._parser().parse_args(
            ["--remote", "server", "deploy", "--os", "debian13", "--cluster", "hpc"]
        )
        self.cli.user_state = UserState(Path(self.tmpdir.name))
        self.cli.preferences = mock.Mock(remote_host=None)
        self.cli.runtime_settings = mock.Mock()
        os_db = mock.patch("firehpc.exec.OSDatabase").start().return_value
        os_db.supported.return_value = True
        os_db.environment.return_value = "ansible-latest"
        os_db.url.return_value = "https://images.example.org/debian13.tar.xz"
        self.addCleanup(mock.patch.stopall)
        self.state = Path(self.tmpdir.name) / "clusters" / "hpc"

    def test_unreachable_host(self):
        mock.patch.object(FireHPCExec, "_load_racksdb").start()
        mock.patch(
            "firehpc.exec.EmulatedCluster.check_host",
            side_effect=FireHPCRuntimeError("Unable to connect to remote host"),
        ).start()
        with self.assertRaises(FireHPCRuntimeError):
            self.cli._execute_deploy()
        self.assertFalse(self.state.exists())

    def test_invalid_racksdb(self):
        mock.patch.object(
            FireHPCExec, "_load_racksdb", side_effect=SystemExit(1)
        ).start()
        check_host = mock.patch("firehpc.exec.EmulatedCluster.check_host").start()
        with self.assertRaises(SystemExit):
            self.cli._execute_deploy()
        check_host.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_settings_saved_after_checks(self):
        mock.patch.object(FireHPCExec, "_load_racksdb").start()
        mock.patch("firehpc.exec.EmulatedCluster.check_host").start()
        deploy = mock.patch(
            "firehpc.exec.EmulatedCluster.deploy",
            side_effect=lambda *args: self.assertTrue(
                (self.state / "settings.yml").exists()
            ),
        ).start()
        mock.patch("firehpc.exec.EmulatedCluster.conf").start()
        self.cli._execute_deploy()
        deploy.assert_called_once()
