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
from pathlib import Path

from racksdb import RacksDB

from .version import get_version
from .settings import RuntimeSettings
from .state import default_state_dir
from .cluster import EmulatedCluster
from .ssh import SSHClient
from .errors import FireHPCRuntimeError
from .images import OSImagesSources
from .log import TTYFormatter
from .dumpers import DumperFactory

logger = logging.getLogger(__name__)


class FireHPCExec:
    @classmethod
    def run(cls):
        cls()

    def __init__(self):
        parser = argparse.ArgumentParser(
            description="Instantly fire up container-based emulated HPC cluster."
        )
        parser.add_argument(
            "-v",
            "--version",
            action="version",
            version="FireHPC " + get_version(),
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Enable debug mode",
        )
        parser.add_argument(
            "--show-libs-logs",
            action="store_true",
            help="Show external libraries logs",
        )
        parser.add_argument(
            "--state",
            help="Directory to store cluster state (default: %(default)s)",
            type=Path,
            default=default_state_dir(),
        )
        subparsers = parser.add_subparsers(
            help="Action to perform",
            dest="action",
            required=True,
        )

        # deploy command
        parser_deploy = subparsers.add_parser("deploy", help="Deploy cluster")
        parser_deploy.add_argument(
            "--db",
            help="Path to RacksDB database (default: %(default)s)",
            type=Path,
            default=RacksDB.DEFAULT_DB,
        )
        parser_deploy.add_argument(
            "--schema",
            help="Path to RacksDB schema (default: %(default)s)",
            type=Path,
            default=RacksDB.DEFAULT_SCHEMA,
        )
        parser_deploy.add_argument(
            "--os",
            help="Operating system to deploy",
            required=True,
        )
        parser_deploy.add_argument(
            "--zone",
            help="Name of the zone to deploy",
            required=True,
        )
        parser_deploy.add_argument(
            "-c",
            "--custom",
            help="Path of variables directories to customize FireHPC default",
            type=Path,
        )
        parser_deploy.set_defaults(func=self._execute_deploy)

        # conf command
        parser_conf = subparsers.add_parser(
            "conf", help="Deploy configuration on cluster"
        )
        parser_conf.add_argument(
            "--db",
            help="Path to RacksDB database (default: %(default)s)",
            type=Path,
            default=RacksDB.DEFAULT_DB,
        )
        parser_conf.add_argument(
            "--schema",
            help="Path to RacksDB schema (default: %(default)s)",
            type=Path,
            default=RacksDB.DEFAULT_SCHEMA,
        )
        parser_conf.add_argument(
            "--zone",
            help="Name of the zone on which configuration is deployed",
            required=True,
        )
        parser_conf.add_argument(
            "-c",
            "--custom",
            help="Path of variables directories to customize FireHPC default",
            type=Path,
        )
        parser_conf.add_argument(
            "--tags",
            help="Configuration tags to deploy",
            nargs="*",
        )
        parser_conf.add_argument(
            "--with-bootstrap",
            action="store_true",
            help="Run configuration bootstrap",
        )
        parser_conf.set_defaults(func=self._execute_conf)

        # ssh command
        parser_ssh = subparsers.add_parser("ssh", help="Connect to cluster zone by SSH")
        parser_ssh.add_argument(
            "args",
            help="Destination node and arguments of SSH connection",
            nargs="+",
        )
        parser_ssh.set_defaults(func=self._execute_ssh)

        # clean command
        parser_clean = subparsers.add_parser("clean", help="Clean cluster zone")
        parser_clean.add_argument(
            "--zone",
            help="Name of the zone to clean",
            required=True,
        )
        parser_clean.set_defaults(func=self._execute_clean)

        # status command
        parser_status = subparsers.add_parser(
            "status", help="Status of cluster in zone"
        )
        parser_status.add_argument(
            "--zone",
            help="Name of the zone",
            required=True,
        )
        parser_status.add_argument(
            "--json",
            action="store_true",
            help="Report cluster status in JSON format",
        )
        parser_status.set_defaults(func=self._execute_status)

        # images command
        parser_images = subparsers.add_parser("images", help="List available OS images")
        parser_images.set_defaults(func=self._execute_images)

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
            lib_filter = logging.Filter("firehpc")  # filter out all libs logs
            handler.addFilter(lib_filter)
        root_logger.addHandler(handler)

    def _load_racksdb(self):
        return RacksDB.load(db=self.args.db, schema=self.args.schema)

    def _execute_deploy(self):
        images = OSImagesSources(self.settings)
        if not images.supported(self.args.os):
            logger.critical("OS %s is not supported", self.args.os)
            logger.info("Run `firehpc images` to get the list of supported OS")
            sys.exit(1)
        db = self._load_racksdb()
        cluster = EmulatedCluster(
            self.settings,
            self.args.zone,
            self.args.state,
        )
        cluster.deploy(self.args.os, images, db)
        cluster.conf(db, custom=self.args.custom)

    def _execute_conf(self):
        cluster = EmulatedCluster(self.settings, self.args.zone, self.args.state)
        cluster.conf(
            self._load_racksdb(),
            reinit=False,
            bootstrap=self.args.with_bootstrap,
            custom=self.args.custom,
            tags=self.args.tags,
        )

    def _execute_ssh(self):
        if "." not in self.args.args[0]:
            logger.critical(
                "Format of ssh command first argument is not valid, it must be "
                "destination node with format: [login@]node.zone"
            )
            sys.exit(1)
        zone = self.args.args[0].split(".")[1]
        cluster = EmulatedCluster(self.settings, zone, self.args.state)
        ssh = SSHClient(cluster)
        ssh.exec(self.args.args)

    def _execute_clean(self):
        cluster = EmulatedCluster(self.settings, self.args.zone, self.args.state)
        cluster.clean()

    def _execute_status(self):
        cluster = EmulatedCluster(self.settings, self.args.zone, self.args.state)
        print(
            DumperFactory.get("json" if self.args.json else "console").dump(
                cluster.status()
            )
        )

    def _execute_images(self):
        images = OSImagesSources(self.settings)
        print(str(images), end="")
