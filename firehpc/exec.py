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

import argparse
import logging
import sys
import os
from pathlib import Path

from .version import __version__
from .settings import RuntimeSettings
from .cluster import EmulatedCluster
from .log import TTYFormatter

logger = logging.getLogger(__name__)


def default_state_dir():
    """Returns the default path to the user state directory, through
    XDG_STATE_HOME environment variable if it is set."""
    return (
        Path(os.getenv('XDG_STATE_HOME', '~/.local/state')).expanduser()
        / 'firehpc'
    )


class FireHPCExec:
    @classmethod
    def run(cls):
        cls()

    def __init__(self):
        parser = argparse.ArgumentParser(
            description='Instantly fire up container-based emulated HPC cluster.'
        )
        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version='FireHPC ' + __version__,
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help="Enable debug mode",
        )
        parser.add_argument(
            '--show-libs-logs',
            action='store_true',
            help="Show external libraries logs",
        )
        parser.add_argument(
            '--os',
            help="Operating system to deploy",
            choices=['debian11', 'rocky8'],
        )
        parser.add_argument(
            '--zone',
            help="Name of the zone to deploy",
        )
        parser.add_argument(
            '--state',
            help="Directory to store cluster state (default: %(default)s)",
            type=Path,
            default=default_state_dir(),
        )

        parser.add_argument(
            'action',
            help="Action to perform",
            choices=['deploy', 'clean'],
        )

        self.args = parser.parse_args()
        self._setup_logger()
        self.settings = RuntimeSettings()
        self._execute()

    def _setup_logger(self):
        if self.args.debug:
            logging_level = logging.DEBUG
        else:
            logging_level = logging.INFO

        root_logger = logging.getLogger()
        root_logger.setLevel(logging_level)
        handler = logging.StreamHandler()
        handler.setLevel(logging_level)
        formatter = TTYFormatter(self.args.debug)
        handler.setFormatter(formatter)
        if not self.args.show_libs_logs:
            lib_filter = logging.Filter('firehpc')  # filter out all libs logs
            handler.addFilter(lib_filter)
        root_logger.addHandler(handler)

    def _execute(self):
        if self.args.action == 'deploy':
            self._execute_deploy()
        elif self.args.action == 'clean':
            self._execute_clean()
        else:
            raise NotImplementedError(
                f"action {self.args.action} is not supported"
            )

    def _execute_deploy(self):
        if self.args.zone is None:
            logger.critical("zone to deploy is not defined")
            logger.info("try setting the zone to deploy with --zone argument")
            sys.exit(1)
        if self.args.os is None:
            logger.critical("operating system to deploy is not defined")
            logger.info("try setting the zone to deploy with --os argument")
            sys.exit(1)
        cluster = EmulatedCluster(
            self.settings, self.args.zone, self.args.os, self.args.state
        )
        cluster.deploy()

    def _execute_clean(self):
        if self.args.zone is None:
            logger.critical("zone to clean is not defined")
            logger.info("try setting the zone to clean with --zone argument")
            sys.exit(1)
        cluster = EmulatedCluster(
            self.settings, self.args.zone, self.args.os, self.args.state
        )
        cluster.clean()
