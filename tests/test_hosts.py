# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from firehpc.errors import FireHPCRuntimeError
from firehpc.hosts import close_hosts, get_host
from firehpc.hosts.local import LocalHost
from firehpc.hosts.remote import RemoteHost, parse_destination
from firehpc.providers import PROVIDERS


class TestParseDestination(unittest.TestCase):
    def test_host(self):
        self.assertEqual(parse_destination("server"), (None, "server", None))

    def test_user_host_port(self):
        self.assertEqual(
            parse_destination("john@server:2222"), ("john", "server", 2222)
        )

    def test_ipv6(self):
        self.assertEqual(parse_destination("::1"), (None, "::1", None))
        self.assertEqual(parse_destination("root@[::1]:22"), ("root", "::1", 22))

    def test_invalid(self):
        for destination in ["", "server:port", "user@", "[::1]x"]:
            with self.subTest(destination=destination):
                with self.assertRaises(FireHPCRuntimeError):
                    parse_destination(destination)


class TestRemoteHostConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.config = Path(self.tmpdir.name) / "config"
        self.config.write_text(
            "Host myserver\n"
            "  HostName server.example.org\n"
            "  User john\n"
            "  Port 2222\n"
            "  IdentityFile /keys/id_ed25519\n"
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_ssh_config(self):
        connection = RemoteHost("myserver", self.config)
        self.assertEqual(connection.hostname, "server.example.org")
        self.assertEqual(connection.user, "john")
        self.assertEqual(connection.port, 2222)
        self.assertEqual(connection.key_filenames, ["/keys/id_ed25519"])
        self.assertIsNone(connection.proxy_command)

    def test_destination_over_ssh_config(self):
        connection = RemoteHost("alice@myserver:22", self.config)
        self.assertEqual(connection.hostname, "server.example.org")
        self.assertEqual(connection.user, "alice")
        self.assertEqual(connection.port, 22)

    def test_without_ssh_config(self):
        connection = RemoteHost("other", Path(self.tmpdir.name) / "missing")
        self.assertEqual(connection.hostname, "other")
        self.assertIsNone(connection.user)
        self.assertEqual(connection.port, 22)


class TestLocalHost(unittest.TestCase):
    def test_local(self):
        host = LocalHost()
        self.assertFalse(host.is_remote)
        self.assertEqual(host.label, "local host")
        self.assertIsNone(host.ssh_proxy_command())
        self.assertEqual(host.ssh_proxy_args(), [])
        self.assertIsNone(host.helper_command())

    def test_provider(self):
        fake = mock.Mock()
        with mock.patch.dict(PROVIDERS, {"fake": fake}):
            self.assertIs(LocalHost().provider("fake", "hpc"), fake.return_value)
        fake.assert_called_once_with("hpc")

    def test_open_tcp(self):
        with mock.patch("socket.create_connection") as create_connection:
            self.assertIs(
                LocalHost().open_tcp("admin.hpc.john", 22),
                create_connection.return_value,
            )
        create_connection.assert_called_once_with(("admin.hpc.john", 22))


class TestRemoteHost(unittest.TestCase):
    def setUp(self):
        mock.patch(
            "firehpc.hosts.remote.firehpc_command", return_value="/usr/bin/firehpc"
        ).start()
        self.addCleanup(mock.patch.stopall)
        self.host = RemoteHost("john@server", Path("/nonexistent"))

    def test_attributes(self):
        self.assertTrue(self.host.is_remote)
        self.assertEqual(self.host.label, "john@server")
        self.assertEqual(self.host.remote, "john@server")

    def test_ssh_proxy(self):
        self.assertEqual(
            self.host.ssh_proxy_command(),
            "/usr/bin/firehpc --remote john@server remote proxy %h %p",
        )
        self.assertEqual(
            self.host.ssh_proxy_args(),
            [
                "-o",
                "ProxyCommand=/usr/bin/firehpc --remote john@server remote proxy %h %p",
            ],
        )

    def test_helper_command(self):
        self.assertEqual(
            self.host.helper_command(),
            ["/usr/bin/firehpc", "--remote", "john@server", "remote"],
        )

    def test_provider(self):
        session = mock.Mock()
        with mock.patch(
            "firehpc.agent.client.AgentSession.start", return_value=session
        ):
            provider = self.host.provider("nspawn", "hpc")
            provider.running()
            # agent session is shared by providers
            self.host.provider("nspawn", "other")
        session.call.assert_called_once_with("nspawn", "hpc", "running", {})
        self.assertIs(self.host.session, session)


class TestGetHost(unittest.TestCase):
    def setUp(self):
        self.addCleanup(close_hosts)

    def test_cache(self):
        self.assertIs(get_host("server"), get_host("server"))
        self.assertIs(get_host(""), get_host(None))
        self.assertIsInstance(get_host(None), LocalHost)
        self.assertIsInstance(get_host("server"), RemoteHost)
