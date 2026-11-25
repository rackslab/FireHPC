# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import socket
import unittest
from unittest import mock

from firehpc.errors import FireHPCRuntimeError
from firehpc.providers import DEFAULT_PROVIDER, PROVIDERS, provider_class
from firehpc.providers.base import MachineProvider
from firehpc.providers.nspawn import NspawnProvider
from firehpc.providers.nspawn.dbus import Container


class TestProviders(unittest.TestCase):
    def test_registry(self):
        self.assertEqual(DEFAULT_PROVIDER, "nspawn")
        for name, cls in PROVIDERS.items():
            with self.subTest(provider=name):
                self.assertEqual(cls.NAME, name)
                self.assertTrue(issubclass(cls, MachineProvider))
        self.assertIs(provider_class("nspawn"), NspawnProvider)

    def test_unknown(self):
        with self.assertRaisesRegex(FireHPCRuntimeError, "Unsupported machine"):
            provider_class("nope")

    def test_methods_implemented(self):
        # Every method exposed through agent is an abstract method of the base
        # class, implemented by all providers.
        self.assertEqual(
            set(MachineProvider.METHODS), MachineProvider.__abstractmethods__
        )
        for cls in PROVIDERS.values():
            with self.subTest(provider=cls.NAME):
                self.assertFalse(cls.__abstractmethods__)

    def test_nspawn(self):
        self.assertEqual(NspawnProvider.BOOTSTRAP_CONNECTION, "machinectl")
        self.assertEqual(NspawnProvider.bootstrap_vars(None), {})
        helper = ["/usr/bin/firehpc", "--remote", "server", "remote"]
        self.assertEqual(
            NspawnProvider.bootstrap_vars(helper),
            {"ansible_machinectl_remote_helper": helper},
        )

    def test_base_bootstrap_vars(self):
        self.assertEqual(MachineProvider.bootstrap_vars(["helper"]), {})


class TestContainerAddresses(unittest.TestCase):
    V4 = (int(socket.AF_INET), (10, 0, 0, 2))
    V6 = (int(socket.AF_INET6), (0xFE, 0x80) + (0,) * 13 + (2,))

    def container(self, *replies):
        # Bypass constructor to avoid connecting to DBus system bus.
        container = Container.__new__(Container)
        container.name = "cn1"
        container.proxy = mock.Mock()
        container.proxy.GetAddresses.side_effect = list(replies)
        return container

    @mock.patch("firehpc.providers.nspawn.dbus.time.sleep")
    def test_wait(self, sleep):
        container = self.container([self.V4], [self.V4, self.V6])
        result = container.addresses()
        # Addresses found in first attempt must not be duplicated.
        self.assertEqual([str(address) for address in result], ["10.0.0.2", "fe80::2"])
        sleep.assert_called_once_with(1)

    @mock.patch("firehpc.providers.nspawn.dbus.time.sleep")
    @mock.patch("firehpc.providers.nspawn.dbus.time.monotonic")
    def test_timeout(self, monotonic, sleep):
        monotonic.side_effect = [0, 30, 61]
        container = self.container([self.V4], [self.V4])
        with self.assertRaisesRegex(
            FireHPCRuntimeError,
            "Timeout after 60 seconds while waiting for IPv6 address of container cn1",
        ):
            container.addresses()

    def test_no_wait(self):
        container = self.container([])
        self.assertEqual(container.addresses(wait=False), [])
