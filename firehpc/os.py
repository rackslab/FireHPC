#!/usr/bin/env python3
#
# Copyright (C) 2023-2025 Rackslab
#
# This file is part of FireHPC.
#
# FireHPC is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# FireHPC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with FireHPC.  If not, see <https://www.gnu.org/licenses/>.

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
        for os, value in self.db.items():
            result += f"{os:10s}: {value['url']}\n"
        return result
