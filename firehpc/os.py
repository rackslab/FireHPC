# Copyright (c) 2023-2025 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Manage OS YAML database."""

from __future__ import annotations
from typing import TYPE_CHECKING
import logging

import yaml

if TYPE_CHECKING:
    from .settings import RuntimeSettings

logger = logging.getLogger(__name__)


class OSDatabase:
    def __init__(self, settings: RuntimeSettings) -> OSDatabase:
        logger.debug("Loading OS database file %s", settings.os.db)
        with open(settings.os.db) as fh:
            self.content = yaml.safe_load(fh)

    def supported(self, os: str) -> bool:
        return os in self.content.keys()

    def url(self, os: str) -> str:
        return self.content[os]["url"]

    def environment(self, os: str) -> str:
        return self.content[os]["environment"]

    def __str__(self):
        result = ""
        for os, value in self.content.items():
            result += f"{os:10s}: {value['url']}\n"
        return result
