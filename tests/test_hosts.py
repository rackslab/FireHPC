# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from unittest import mock

from firehpc.errors import FireHPCRuntimeError
from firehpc.hosts import close_hosts, get_host
from firehpc.hosts.local import LocalHost
from firehpc.providers import PROVIDERS


class TestLocalHost(unittest.TestCase):
    def test_local(self):
        host = LocalHost()
        self.assertFalse(host.is_remote)
        self.assertEqual(host.label, "local host")
        self.assertIsNone(host.ssh_proxy_command())
        self.assertEqual(host.ssh_proxy_args(), [])

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


class TestGetHost(unittest.TestCase):
    def setUp(self):
        self.addCleanup(close_hosts)

    def test_cache(self):
        self.assertIs(get_host(""), get_host(None))
        self.assertIsInstance(get_host(None), LocalHost)

    def test_remote_unsupported(self):
        with self.assertRaises(FireHPCRuntimeError):
            get_host("server")
