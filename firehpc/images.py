#!/usr/bin/env python3
#
# Copyright (C) 2023 Rackslab
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

from __future__ import annotations
from typing import TYPE_CHECKING
import logging

import yaml

if TYPE_CHECKING:
    from .settings import RuntimeSettings

logger = logging.getLogger(__name__)


class OSImagesSources:
    def __init__(self, settings: RuntimeSettings) -> OSImagesSources:
        logger.debug("Loading OS images sources file %s", settings.images.sources)
        with open(settings.images.sources) as fh:
            self.sources = yaml.safe_load(fh)

    def url(self, os: str) -> str:
        return self.sources[os]

    def __str__(self):
        result = ""
        for os, url in self.sources.items():
            result += f"{os:10s}: {url}\n"
        return result
