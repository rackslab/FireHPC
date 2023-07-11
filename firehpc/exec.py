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
from .ssh import SSHClient
from .errors import FireHPCRuntimeError
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
            '--state',
            help="Directory to store cluster state (default: %(default)s)",
            type=Path,
            default=default_state_dir(),
        )
        subparsers = parser.add_subparsers(
            help='Action to perform',
            dest='action',
            required=True,
        )

        # deploy command
        parser_deploy = subparsers.add_parser('deploy', help='Deploy cluster')
        parser_deploy.add_argument(
            '--os',
            help="Operating system to deploy",
            choices=['debian11', 'rocky8'],
            required=True,
        )
        parser_deploy.add_argument(
            '--zone',
            help="Name of the zone to deploy",
            required=True,
        )
        parser_deploy.set_defaults(func=self._execute_deploy)

        # conf command
        parser_conf = subparsers.add_parser(
            'conf', help='Deploy configuration on cluster'
        )
        parser_conf.add_argument(
            '--zone',
            help="Name of the zone on which configuration is deployed",
            required=True,
        )
        parser_conf.add_argument(
            '--with-bootstrap',
            action='store_true',
            help="Run configuration bootstrap",
        )
        parser_conf.set_defaults(func=self._execute_conf)

        # ssh command
        parser_ssh = subparsers.add_parser(
            'ssh', help='Connect to cluster zone by SSH'
        )
        parser_ssh.add_argument(
            'args',
            help="Destination node and arguments of SSH connection",
            nargs='+',
        )
        parser_ssh.set_defaults(func=self._execute_ssh)

        # clean command
        parser_clean = subparsers.add_parser('clean', help='Clean cluster zone')
        parser_clean.add_argument(
            '--zone',
            help="Name of the zone to clean",
            required=True,
        )
        parser_clean.set_defaults(func=self._execute_clean)

        self.args = parser.parse_args()
        self._setup_logger()
        self.settings = RuntimeSettings()
        try:
            self.args.func()
        except FireHPCRuntimeError as e:
            logger.critical(str(e))
            sys.exit(1)

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

    def _execute_deploy(self):
        cluster = EmulatedCluster(
            self.settings, self.args.zone, self.args.os, self.args.state
        )
        cluster.deploy()
        cluster.conf()

    def _execute_conf(self):
        cluster = EmulatedCluster(
            self.settings, self.args.zone, None, self.args.state
        )
        cluster.conf(reinit=False, bootstrap=self.args.with_bootstrap)

    def _execute_ssh(self):
        if '.' not in self.args.args[0]:
            logger.critical(
                "Format of ssh command first argument is not valid, it must be "
                "destination node with format: [login@]node.zone"
            )
            sys.exit(1)
        zone = self.args.args[0].split('.')[1]
        cluster = EmulatedCluster(self.settings, zone, None, self.args.state)
        ssh = SSHClient(cluster)
        ssh.exec(self.args.args)

    def _execute_clean(self):
        cluster = EmulatedCluster(
            self.settings, self.args.zone, None, self.args.state
        )
        cluster.clean()
