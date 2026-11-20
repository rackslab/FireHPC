# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from firehpc.errors import FireHPCRuntimeError
from firehpc.providers import DEFAULT_PROVIDER, PROVIDERS, provider_class
from firehpc.providers.base import MachineProvider
from firehpc.providers.nspawn import NspawnProvider


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
