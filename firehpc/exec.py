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
from racksdb.errors import RacksDBFormatError, RacksDBSchemaError

from .version import get_version
from .settings import RuntimeSettings, ClusterSettings
from .state import default_state_dir, UserState, ClusterState
from .cluster import EmulatedCluster, clusters_list
from .environments import bootstrap
from .ssh import SSHClient
from .errors import FireHPCRuntimeError
from .os import OSDatabase
from .load import load_clusters
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

        # bootstrap command
        parser_bootstrap = subparsers.add_parser(
            "bootstrap", help="Bootstrap deployment environments"
        )
        parser_bootstrap.set_defaults(func=self._execute_bootstrap)

        # deploy command
        parser_deploy = subparsers.add_parser("deploy", help="Deploy cluster")
        parser_deploy.add_argument(
            "--db",
            help="Path to RacksDB database",
            type=Path,
        )
        parser_deploy.add_argument(
            "--schema",
            help="Path to RacksDB schema",
            type=Path,
        )
        parser_deploy.add_argument(
            "--os",
            help="Operating system to deploy",
            required=True,
        )
        parser_deploy.add_argument(
            "--cluster",
            help="Name of the cluster to deploy",
            required=True,
        )
        parser_deploy.add_argument(
            "-c",
            "--custom",
            help="Path of variables directories to customize FireHPC default",
            type=Path,
        )
        parser_deploy.add_argument(
            "--slurm-emulator",
            help="Enable Slurm emulator mode",
            action="store_true",
        )
        parser_deploy.add_argument(
            "--users",
            help="Extract users directory from another emulated cluster",
        )
        parser_deploy.set_defaults(func=self._execute_deploy)

        # conf command
        parser_conf = subparsers.add_parser(
            "conf", help="Deploy configuration on cluster"
        )
        parser_conf.add_argument(
            "--db",
            help="Path to RacksDB database",
            type=Path,
        )
        parser_conf.add_argument(
            "--schema",
            help="Path to RacksDB schema",
            type=Path,
        )
        parser_conf.add_argument(
            "--cluster",
            help="Name of the cluster on which configuration is deployed",
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
        parser_conf.add_argument(
            "--slurm-emulator",
            help="Enable Slurm emulator mode",
            action="store_true",
        )
        parser_conf.set_defaults(func=self._execute_conf)

        # restore command
        parser_restore = subparsers.add_parser(
            "restore", help="Restore cluster state after restart or IP change"
        )
        parser_restore.add_argument(
            "--db",
            help="Path to RacksDB database",
            type=Path,
        )
        parser_restore.add_argument(
            "--schema",
            help="Path to RacksDB schema",
            type=Path,
        )
        parser_restore.add_argument(
            "--cluster",
            help="Name of the cluster on which configuration is deployed",
            required=True,
        )
        parser_restore.add_argument(
            "-c",
            "--custom",
            help="Path of variables directories to customize FireHPC default",
            type=Path,
        )
        parser_restore.add_argument(
            "--slurm-emulator",
            help="Enable Slurm emulator mode",
            action="store_true",
        )
        parser_restore.set_defaults(func=self._execute_restore)

        # ssh command
        parser_ssh = subparsers.add_parser("ssh", help="Connect to cluster by SSH")
        parser_ssh.add_argument(
            "args",
            help="Destination node and arguments of SSH connection",
            nargs="+",
        )
        parser_ssh.set_defaults(func=self._execute_ssh)

        # clean command
        parser_clean = subparsers.add_parser("clean", help="Clean emulated cluster")
        parser_clean.add_argument(
            "--cluster",
            help="Name of the cluster to clean",
            required=True,
        )
        parser_clean.set_defaults(func=self._execute_clean)

        # start command
        parser_start = subparsers.add_parser(
            "start", help="Start an already deployed cluster"
        )
        parser_start.add_argument(
            "--cluster",
            help="Name of the cluster to start",
            required=True,
        )
        parser_start.set_defaults(func=self._execute_start)

        # stop command
        parser_stop = subparsers.add_parser("stop", help="Stop a cluster")
        parser_stop.add_argument(
            "--cluster",
            help="Name of the cluster to stop",
            required=True,
        )
        parser_stop.set_defaults(func=self._execute_stop)

        # status command
        parser_status = subparsers.add_parser("status", help="Status of cluster")
        parser_status.add_argument(
            "--cluster",
            help="Name of the cluster",
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

        # list command
        parser_list = subparsers.add_parser("list", help="List existing clusters")
        parser_list.set_defaults(func=self._execute_list)

        # load command
        parser_load = subparsers.add_parser("load", help="Load clusters with jobs")
        parser_load.add_argument(
            "clusters",
            metavar="CLUSTER",
            help="Destination clusters",
            nargs="+",
        )
        parser_load.add_argument(
            "--time-off-factor",
            help=(
                "Divide load by this factor outside business hours (default: "
                "%(default)s)"
            ),
            type=int,
            default=5,
        )
        parser_load.set_defaults(func=self._execute_load)

        # update command
        parser_update = subparsers.add_parser("update", help="Update cluster settings")
        parser_update.add_argument(
            "--cluster",
            help="Name of the cluster",
            required=True,
        )
        parser_update.add_argument(
            "--db",
            help="New path to RacksDB database",
            type=Path,
        )
        parser_update.add_argument(
            "--schema",
            help="New path to RacksDB schema",
            type=Path,
        )
        parser_update.add_argument(
            "-c",
            "--custom",
            help="New path of variables directories to customize FireHPC default",
            type=Path,
        )
        parser_update.add_argument(
            "--slurm-emulator",
            help="Enable Slurm emulator mode",
            action="store_true",
        )
        parser_update.set_defaults(func=self._execute_update)

        self.args = parser.parse_args()
        self._setup_logger()
        self.runtime_settings = RuntimeSettings()
        self.user_state = UserState(self.args.state)
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

    def _load_racksdb(self, settings: ClusterSettings):
        try:
            return RacksDB.load(db=settings.racksdb.db, schema=settings.racksdb.schema)
        except (RacksDBSchemaError, RacksDBFormatError) as err:
            logger.critical("Unable to load RacksDB database: %s", err)
            sys.exit(1)

    def _execute_bootstrap(self):
        bootstrap(self.user_state, self.runtime_settings)

    def _execute_deploy(self):
        # Load images sources
        os_db = OSDatabase(self.runtime_settings)
        if not os_db.supported(self.args.os):
            logger.critical("OS %s is not supported", self.args.os)
            logger.info("Run `firehpc images` to get the list of supported OS")
            sys.exit(1)

        # Define cluster settings from args and save
        state = ClusterState(self.user_state, self.args.cluster)
        state.create()
        cluster_settings = ClusterSettings.from_values(
            os=self.args.os,
            environment=os_db.environment(self.args.os),
            slurm_emulator=self.args.slurm_emulator,
            db=self.args.db,
            schema=self.args.schema,
            custom=self.args.custom,
        )
        state.save(cluster_settings)

        # Load RacksDB
        db = self._load_racksdb(cluster_settings)

        # Initialize cluster
        cluster = EmulatedCluster(
            self.runtime_settings, self.args.cluster, state, cluster_settings
        )

        # If user specified another cluster name to extract its users directory, load
        # this users directory.
        users_directory = None
        if self.args.users:
            users_cluster_state = ClusterState(self.user_state, self.args.users)
            logger.info("Extracting users directory from cluster %s", self.args.users)
            users_directory = EmulatedCluster(
                self.runtime_settings,
                self.args.users,
                users_cluster_state,
                users_cluster_state.load(),
            ).users_directory

        # Deploy cluster
        cluster.deploy(self.args.os, os_db.url(self.args.os), db)
        cluster.conf(
            db,
            playbooks=["bootstrap", "site"],
            users_directory=users_directory,
        )

    def _execute_conf(self):
        # Load cluster settings
        state = ClusterState(self.user_state, self.args.cluster)
        cluster_settings = state.load()
        # Update settings with provided args
        cluster_settings.update_from_args(self.args)

        cluster = EmulatedCluster(
            self.runtime_settings, self.args.cluster, state, cluster_settings
        )
        settings = cluster.load()
        settings.update_from_args(self.args)
        cluster.save(settings)

        playbooks = ["site"]
        if self.args.with_bootstrap:
            playbooks.insert(0, "bootstrap")
        cluster.conf(
            self._load_racksdb(cluster_settings),
            playbooks=playbooks,
            reinit=False,
            tags=self.args.tags,
        )

    def _execute_restore(self):
        # Load cluster settings
        state = ClusterState(self.user_state, self.args.cluster)
        cluster_settings = state.load()
        # Update settings with provided args
        cluster_settings.update_from_args(self.args)

        cluster = EmulatedCluster(
            self.runtime_settings, self.args.cluster, state, cluster_settings
        )
        cluster.conf(
            self._load_racksdb(cluster_settings),
            playbooks=["restore"],
            reinit=False,
            skip_tags=["dependencies"],  # skip slurm->mariadb dependency
        )

    def _execute_start(self):
        # Load cluster settings
        state = ClusterState(self.user_state, self.args.cluster)
        cluster_settings = state.load()

        cluster = EmulatedCluster(
            self.runtime_settings, self.args.cluster, state, cluster_settings
        )
        cluster.start()

    def _execute_stop(self):
        # Load cluster settings
        state = ClusterState(self.user_state, self.args.cluster)
        cluster_settings = state.load()

        cluster = EmulatedCluster(
            self.runtime_settings, self.args.cluster, state, cluster_settings
        )
        cluster.stop()

    def _execute_ssh(self):
        # Define cluster name
        cluster_name = self.args.args[0]
        if "." in self.args.args[0]:
            cluster_name = cluster_name.split(".")[1]

        # Load cluster settings
        state = ClusterState(self.user_state, cluster_name)
        cluster_settings = state.load()

        cluster = EmulatedCluster(
            self.runtime_settings, cluster_name, state, cluster_settings
        )
        ssh = SSHClient(cluster)
        ssh.exec(self.args.args)

    def _execute_clean(self):
        # Load cluster settings
        state = ClusterState(self.user_state, self.args.cluster)

        cluster = EmulatedCluster(self.runtime_settings, self.args.cluster, state)
        cluster.clean()

    def _execute_status(self):
        # Load cluster settings
        state = ClusterState(self.user_state, self.args.cluster)
        cluster_settings = state.load()

        cluster = EmulatedCluster(
            self.runtime_settings, self.args.cluster, state, cluster_settings
        )
        print(
            DumperFactory.get("json" if self.args.json else "console").dump(
                cluster.status()
            )
        )

    def _execute_images(self):
        os_db = OSDatabase(self.runtime_settings)
        print(str(os_db), end="")

    def _execute_list(self):
        print("\n".join(clusters_list(self.args.state)))

    def _execute_load(self):
        load_clusters(
            self.runtime_settings,
            self.args.clusters,
            self.user_state,
            self.args.time_off_factor,
        )

    def _execute_update(self):
        # Load cluster settings
        state = ClusterState(self.user_state, self.args.cluster)
        cluster_settings = state.load()
        # Update settings with provided args
        cluster_settings.update_from_args(self.args)
        state.save(cluster_settings)
