# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import unittest

from firehpc.load import JOB_NAMES

_JOB_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_. ]*$")
_MAX_JOB_NAME_LEN = 64


class TestLoadJobNames(unittest.TestCase):
    def test_job_names_format_and_length(self):
        self.assertGreaterEqual(len(JOB_NAMES), 35)
        self.assertLessEqual(len(JOB_NAMES), 45)
        for name in JOB_NAMES:
            with self.subTest(name=name):
                self.assertRegex(name, _JOB_NAME_RE)
                self.assertEqual(name, name.strip())
                self.assertNotIn("  ", name)
                self.assertLessEqual(len(name), _MAX_JOB_NAME_LEN)
