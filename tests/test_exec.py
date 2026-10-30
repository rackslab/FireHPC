# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import contextlib
import io
import unittest

from firehpc.exec import MIN_USERS, FireHPCExec


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
