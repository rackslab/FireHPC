# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from firehpc.users import UsersDirectory

GROUP_NAMES = ["scientists", "admin", "biology", "physic", "acoustic", "optic"]


class TestUsersDirectory(unittest.TestCase):
    def test_default_size(self):
        directory = UsersDirectory(10, "hpc")
        logins = [user.login for user in directory]
        self.assertEqual(len(directory.users), 10)
        # Check that the logins are unique.
        self.assertEqual(len(logins), len(set(logins)))
        self.assertEqual([group.name for group in directory.groups], GROUP_NAMES)

    def test_large_size(self):
        directory = UsersDirectory(200, "hpc")
        logins = [user.login for user in directory]
        self.assertEqual(len(directory.users), 200)
        # Check that the logins are unique.
        self.assertEqual(len(logins), len(set(logins)))
        self.assertEqual([group.name for group in directory.groups], GROUP_NAMES)

    def test_load(self):
        directory = UsersDirectory.load(
            "hpc",
            [{"firstname": "Ada", "lastname": "Lovelace"}],
            [{"name": "scientists", "members": ["alovelace"], "parent": "root"}],
        )
        self.assertEqual([user.login for user in directory], ["alovelace"])
        self.assertEqual(directory.groups[0].name, "scientists")
