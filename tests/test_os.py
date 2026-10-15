# Copyright (c) 2025 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path
from types import SimpleNamespace

from firehpc.os import OSDatabase


class TestOSDatabase(unittest.TestCase):
    def _os_db(self):
        repo_root = Path(__file__).resolve().parents[1]
        settings = SimpleNamespace(
            os=SimpleNamespace(db=repo_root / "etc" / "os" / "db.yml")
        )
        return OSDatabase(settings)

    def test_image_name(self):
        os_db = self._os_db()
        self.assertEqual(os_db.image_name("debian13"), "node-debian13_1")
        self.assertEqual(os_db.image_name("rocky8"), "node-rocky8_1")
