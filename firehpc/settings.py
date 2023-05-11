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

import configparser
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RuntimeSettingsAnsible:
    SECTION = 'ansible'

    def __init__(self, config):
        self.path = Path(config.get(self.SECTION, 'path'))
        self.args = config.get(self.SECTION, 'args')


class RuntimeSettings:
    """Settings from configuration files."""

    VENDOR_PATH = Path('/usr/share/firehpc/firehpc.ini')
    SITE_PATH = Path('/etc/firehpc/firehpc.ini')

    def __init__(self):
        _config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation()
        )
        # read vendor configuration file and override with site specific
        # configuration file
        logger.debug("Loading vendor configuration file %s", self.VENDOR_PATH)
        _config.read_file(open(self.VENDOR_PATH))
        if self.SITE_PATH.exists():
            logger.debug(
                "Loading site specific configuration file %s", self.SITE_PATH
            )
            _config.read_file(open(self.SITE_PATH))

        self.ansible = RuntimeSettingsAnsible(_config)
