# Copyright (c) 2023-2025 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import logging
import shlex
import sys
from pathlib import Path

from racksdb import RacksDB
from racksdb.errors import RacksDBFormatError, RacksDBSchemaError

from .version import get_version
from .settings import (
    RuntimeSettings,
    ClusterSettings,
    UserPreferences,
    explicit_remote,
    resolve_remote,
)
from .state import default_state_dir, UserState, ClusterState
from .cluster import EmulatedCluster, clusters_list
from .environments import bootstrap
from .ssh import SSHClient
from .hosts import get_host
from .hosts.remote import RemoteHost, relay
from .errors import FireHPCRuntimeError
from .os import OSDatabase
from .load import load_clusters
from .log import TTYFormatter
from .dumpers import DumperFactory

logger = logging.getLogger(__name__)

# Groups and the primary POSIX group require at least five accounts.
MIN_USERS = 5


def users_count(value: str) -> int:
    """Parse deploy --users. Reject directories too small for the group layout."""
    try:
        count = int(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError(f"invalid integer value: {value!r}") from err
    if count < MIN_USERS:
        raise argparse.ArgumentTypeError(
            f"number of users must be at least {MIN_USERS}"
        )
    return count


class FireHPCExec:
    @classmethod
    def run(cls):
        cls()

    def __init__(self):
        parser = self._parser()
        self.args = parser.parse_args()
        self._setup_logger()
        try:
            self.preferences = UserPreferences()
            RemoteHost.agent_command = self.preferences.remote_agent
            self.runtime_settings = RuntimeSettings()
            self.user_state = UserState(self.args.state)
            self.args.func()
        except FireHPCRuntimeError as e:
            logger.critical(str(e))
            sys.exit(1)

    def _parser(self):
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
        remote_options = parser.add_mutually_exclusive_group()
        remote_options.add_argument(
            "--remote",
            metavar="[USER@]HOST[:PORT]",
            help=(
                "Remote host where cluster containers are deployed (default: "
                "FIREHPC_REMOTE environment variable or user preferences)"
            ),
        )
        remote_options.add_argument(
            "--local",
            action="store_true",
            help="Deploy cluster containers on local host",
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
            "--update-os-image",
            help="Force OS image download",
            action="store_true",
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
        users_options = parser_deploy.add_mutually_exclusive_group()
        users_options.add_argument(
            "--users",
            help="Number of users to generate in directory (default: %(default)s)",
            type=users_count,
            default=10,
        )
        users_options.add_argument(
            "--users-from",
            help="Extract users directory from another emulated cluster",
        )
        parser_deploy.add_argument(
            "--ansible-opts",
            help="Additional ansible-playbook options",
            nargs="*",
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
        parser_conf.add_argument(
            "--ansible-opts",
            help="Additional ansible-playbook options",
            nargs="*",
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

        # remote command, internal helpers for ssh and ansible, hidden from help
        parser_remote = subparsers.add_parser("remote")
        remote_subparsers = parser_remote.add_subparsers(
            dest="remote_action", required=True
        )
        parser_remote_proxy = remote_subparsers.add_parser("proxy")
        parser_remote_proxy.add_argument("host")
        parser_remote_proxy.add_argument("port", type=int)
        parser_remote_proxy.set_defaults(func=self._execute_remote_proxy)
        parser_remote_exec = remote_subparsers.add_parser("exec")
        parser_remote_exec.add_argument("cmd", nargs=argparse.REMAINDER)
        parser_remote_exec.set_defaults(func=self._execute_remote_exec)
        parser_remote_upload = remote_subparsers.add_parser("upload")
        parser_remote_upload.add_argument("source")
        parser_remote_upload.add_argument("destination")
        parser_remote_upload.set_defaults(func=self._execute_remote_upload)
        parser_remote_download = remote_subparsers.add_parser("download")
        parser_remote_download.add_argument("source")
        parser_remote_download.add_argument("destination")
        parser_remote_download.set_defaults(func=self._execute_remote_download)
        # Hide remote command from the list of choices in help, commands without
        # help are not present in choices actions.
        subparsers.metavar = (
            "{" + ",".join(action.dest for action in subparsers._choices_actions) + "}"
        )

        return parser

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

    def _load_cluster(self, name: str) -> EmulatedCluster:
        """Load cluster settings from state and return emulated cluster. Fail if a
        remote host is explicitly requested and differs from the cluster's host."""
        state = ClusterState(self.user_state, name)
        cluster_settings = state.load()
        self._check_remote(name, cluster_settings.remote)
        return EmulatedCluster(self.runtime_settings, name, state, cluster_settings)

    def _check_remote(self, name: str, remote) -> None:
        requested = explicit_remote(self.args)
        if requested is None:
            return
        if (requested or None) != remote:
            raise FireHPCRuntimeError(
                f"Cluster {name} is deployed on {remote or 'local host'}, not on "
                f"{requested or 'local host'}"
            )

    def _execute_bootstrap(self):
        bootstrap(self.user_state, self.runtime_settings)

    def _execute_deploy(self):
        # Load images sources
        os_db = OSDatabase(self.runtime_settings)
        if not os_db.supported(self.args.os):
            logger.critical("OS %s is not supported", self.args.os)
            logger.info("Run `firehpc images` to get the list of supported OS")
            sys.exit(1)

        remote = resolve_remote(self.args, self.preferences)

        # When another cluster users directory is requested, check it is on the
        # same host.
        if self.args.users_from:
            users_cluster_settings = ClusterState(
                self.user_state, self.args.users_from
            ).load()
            if users_cluster_settings.remote != remote:
                raise FireHPCRuntimeError(
                    f"Cluster {self.args.users_from} is deployed on "
                    f"{users_cluster_settings.remote or 'local host'}, it must be on "
                    f"the same host as cluster {self.args.cluster} "
                    f"({remote or 'local host'})"
                )

        # Define cluster settings from args and save
        state = ClusterState(self.user_state, self.args.cluster)
        if state.settings.exists():
            existing_remote = state.load().remote
            if existing_remote != remote:
                raise FireHPCRuntimeError(
                    f"Cluster {self.args.cluster} is already deployed on "
                    f"{existing_remote or 'local host'}, clean it first"
                )
        state.create()
        cluster_settings = ClusterSettings.from_values(
            os=self.args.os,
            environment=os_db.environment(self.args.os),
            slurm_emulator=self.args.slurm_emulator,
            db=self.args.db,
            schema=self.args.schema,
            custom=self.args.custom,
            remote=remote,
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
        if self.args.users_from:
            users_cluster_state = ClusterState(self.user_state, self.args.users_from)
            logger.info(
                "Extracting users directory from cluster %s", self.args.users_from
            )
            users_directory = EmulatedCluster(
                self.runtime_settings,
                self.args.users_from,
                users_cluster_state,
                users_cluster_state.load(),
            ).users_directory

        # Deploy cluster
        cluster.deploy(os_db.url(self.args.os), self.args.update_os_image, db)
        cluster.conf(
            db,
            playbooks=["bootstrap", "site"],
            users_directory=users_directory,
            ansible_opts=self.args.ansible_opts,
            users=self.args.users,
        )

    def _execute_conf(self):
        # Load cluster settings
        cluster = self._load_cluster(self.args.cluster)
        cluster_settings = cluster.cluster_settings
        # Update settings with provided args
        cluster_settings.update_from_args(self.args)

        playbooks = ["site"]
        if self.args.with_bootstrap:
            playbooks.insert(0, "bootstrap")
        cluster.conf(
            self._load_racksdb(cluster_settings),
            playbooks=playbooks,
            reinit=False,
            tags=self.args.tags,
            ansible_opts=self.args.ansible_opts,
        )

    def _execute_restore(self):
        # Load cluster settings
        cluster = self._load_cluster(self.args.cluster)
        cluster_settings = cluster.cluster_settings
        # Update settings with provided args
        cluster_settings.update_from_args(self.args)
        cluster.conf(
            self._load_racksdb(cluster_settings),
            playbooks=["restore"],
            reinit=False,
            skip_tags=["dependencies"],  # skip slurm->mariadb dependency
        )

    def _execute_start(self):
        self._load_cluster(self.args.cluster).start()

    def _execute_stop(self):
        self._load_cluster(self.args.cluster).stop()

    def _execute_ssh(self):
        # Define cluster name
        cluster_name = self.args.args[0]
        if "." in self.args.args[0]:
            cluster_name = cluster_name.split(".")[1]

        ssh = SSHClient(self._load_cluster(cluster_name))
        ssh.exec(self.args.args)

    def _execute_clean(self):
        # Load cluster settings when available to get the cluster host. Otherwise,
        # fallback to requested remote host.
        state = ClusterState(self.user_state, self.args.cluster)
        if state.settings.exists():
            cluster = self._load_cluster(self.args.cluster)
        else:
            cluster = EmulatedCluster(
                self.runtime_settings,
                self.args.cluster,
                state,
                remote=resolve_remote(self.args, self.preferences),
            )
        cluster.clean()

    def _execute_status(self):
        cluster = self._load_cluster(self.args.cluster)
        print(
            DumperFactory.get("json" if self.args.json else "console").dump(
                cluster.status()
            )
        )

    def _execute_images(self):
        os_db = OSDatabase(self.runtime_settings)
        print(str(os_db), end="")

    def _execute_list(self):
        for name in clusters_list(self.args.state):
            try:
                remote = ClusterState(self.user_state, name).load().remote
            except FireHPCRuntimeError:
                remote = None
            print(f"{name} ({remote})" if remote else name)

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

    def _remote_host(self) -> RemoteHost:
        remote = resolve_remote(self.args, self.preferences)
        if remote is None:
            raise FireHPCRuntimeError("Remote host must be defined for this command")
        return get_host(remote)

    def _execute_remote_proxy(self):
        channel = self._remote_host().open_tcp(self.args.host, self.args.port)
        relay(channel, sys.stdin.fileno(), sys.stdout.fileno())

    def _execute_remote_exec(self):
        cmd = self.args.cmd
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        if not cmd:
            raise FireHPCRuntimeError("Command to run on remote host is required")
        sys.exit(
            self._remote_host().run(
                shlex.join(cmd),
                sys.stdin.fileno(),
                sys.stdout.fileno(),
                sys.stderr.fileno(),
            )
        )

    def _execute_remote_upload(self):
        self._remote_host().upload(self.args.source, self.args.destination)

    def _execute_remote_download(self):
        self._remote_host().download(self.args.source, self.args.destination)
