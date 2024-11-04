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
import argparse
from pathlib import Path
import logging
import sys
import json
import random
import time
import threading
from collections import namedtuple

from .version import get_version
from .settings import RuntimeSettings
from .state import default_state_dir
from .cluster import EmulatedCluster
from .ssh import SSHClient
from .errors import FireHPCRuntimeError
from .log import TTYFormatter

if TYPE_CHECKING:
    from .users import UserEntry

logger = logging.getLogger(__name__)


ClusterPartition = namedtuple("ClusterPartition", ["name", "nodes", "cpus", "time"])


class ClusterJobsLoader:
    def __init__(self, cluster: EmulatedCluster):
        self.cluster = cluster
        self.ssh = SSHClient(self.cluster, asbin=False)
        self.stop = False
        # Initialized in run()
        self.select_type = None

    def run(self) -> None:
        logger.info("cluster %s: started running jobs loader", self.cluster.name)
        status = self.cluster.status()

        def random_partition():
            """Select randomly one partition weighted by their number of nodes."""
            return random.choices(
                partitions, [partition.nodes for partition in partitions]
            )[0]

        def total_nodes():
            """Return total number of nodes in all partitions."""
            return sum([partition.nodes for partition in partitions])

        try:
            self.select_type = self._get_select_type()
            partitions = self._get_partitions()
            logger.info(
                "cluster %s: partitions found: %s", self.cluster.name, partitions
            )
            qos = self._get_qos()
            logger.info("cluster %s: QOS found: %s", self.cluster.name, qos)

            # Formula to have jobs limit that grows less than the number of nodes. With
            # this formula, we have:
            #   2 nodes: 12 jobs
            #   10 nodes: 64 jobs
            #   100 nodes: 270 jobs
            #   1000 nodes: 918 jobs
            pending_jobs_limit = int(30 * (total_nodes() ** 0.5) - 30)

            while not self.stop:
                pending_jobs = self._get_nb_pending_jobs()
                if pending_jobs >= pending_jobs_limit:
                    logger.debug(
                        "cluster %s: Waiting for pending jobs to run…",
                        self.cluster.name,
                    )
                    time.sleep(5)
                else:
                    nb_submit = pending_jobs_limit - pending_jobs
                    logger.info(
                        "cluster %s: %s new jobs to submit",
                        self.cluster.name,
                        nb_submit,
                    )
                    while nb_submit:
                        user = random.choice(status.directory.users)
                        self._launch_job(user, random.choice(qos), random_partition())
                        nb_submit -= 1
        except FireHPCRuntimeError as err:
            logger.critical(
                "cluster %s: emulator thread failed with error: %s",
                self.cluster.name,
                str(err),
            )
        logger.info("cluster %s: jobs loader is stopping", self.cluster.name)

    def _get_select_type(self) -> str | None:
        stdout, stderr = self.ssh.exec(
            [f"admin.{self.cluster.name}", "scontrol", "show", "config"]
        )
        result = None
        for line in stdout.decode().split("\n"):
            if line.startswith("SelectType "):
                result = line.split(" = ")[1]
        return result

    def _get_partitions(self) -> list[str]:
        stdout, stderr = self.ssh.exec(
            [f"admin.{self.cluster.name}", "scontrol", "show", "partitions", "--json"]
        )
        try:
            return [
                ClusterPartition(
                    partition["name"],
                    partition["nodes"]["total"],
                    partition["cpus"]["total"],
                    partition["maximums"]["time"],
                )
                for partition in json.loads(stdout)["partitions"]
            ]
        except json.decoder.JSONDecodeError as err:
            raise FireHPCRuntimeError(
                f"Unable to retrieve partitions from cluster {self.cluster.name}: "
                f"{str(err)}"
            ) from err

    def _get_qos(self) -> list[str]:
        stdout, stderr = self.ssh.exec(
            [f"admin.{self.cluster.name}", "sacctmgr", "show", "qos", "--json"]
        )
        try:
            qos_output = json.loads(stdout)
            # QOS key has changed to lower case in Slurm 24.05
            qos_key = "qos" if "qos" in qos_output else "QOS"
            return [qos["name"] for qos in json.loads(stdout)[qos_key]]
        except json.decoder.JSONDecodeError as err:
            raise FireHPCRuntimeError(
                f"Unable to retrieve qos from cluster {self.cluster.name}: {str(err)}"
            ) from err

    def _get_nb_pending_jobs(self):
        stdout, stderr = self.ssh.exec(
            [f"admin.{self.cluster.name}", "squeue", "--state", "pending", "--json"]
        )
        try:
            return len(json.loads(stdout)["jobs"])
        except json.decoder.JSONDecodeError as err:
            raise FireHPCRuntimeError(
                f"Unable to retrieve pending jobs from cluster {self.cluster.name}: "
                f"{str(err)}"
            ) from err

    def _launch_job(
        self, user: UserEntry, qos: str, partition: ClusterPartition
    ) -> None:
        logger.info(
            "cluster %s: submitting job for user %s on partition %s with QOS %s",
            self.cluster.name,
            user.login,
            partition.name,
            qos,
        )
        # If there is only one container, consider the cluster is using emulator mode
        # and submit job on admin node. Otherwise, submit job on login node.
        if len(self.cluster.status().containers) == 1:
            dest = "admin"
        else:
            dest = "login"
        if partition.time["set"]:
            timelimit = str(partition.time["number"])
        else:
            timelimit = "1:0:0"  # 1 hour
        cmd = [
            f"{user.login}@{dest}.{self.cluster.name}",
            "sbatch",
            "--qos",
            qos,
            "--partition",
            partition.name,
            "--time",
            timelimit,
            "--wrap",
            "/usr/bin/sleep 360",
        ]

        def random_power_two(limit: int) -> int:
            """Select randomly one power of two below the limit."""
            i = 1
            possible_values = []
            while i <= limit:
                possible_values.append(i)
                i *= 2
            weights = [
                min(512, 2 ** (len(possible_values) - index[0] - 1))
                for index in enumerate(possible_values)
            ]
            return random.choices(possible_values, weights)[0]

        # If select/linear, allocate a number of nodes, else allocates a number
        # of tasks.
        if self.select_type == "select/linear":
            cmd.extend(["--nodes", str(random_power_two(partition.nodes))])
        else:
            cmd.extend(["--ntasks", str(random_power_two(partition.cpus))])

        self.ssh.exec(cmd)


class FireHPCUsageEmulator:
    @classmethod
    def run(cls):
        cls()

    def __init__(self):
        parser = argparse.ArgumentParser(
            description="Emulate Slurm usage on FireHPC cluster."
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
        parser.add_argument(
            "clusters",
            metavar="cluster",
            help="Cluster to run usage emulation.",
            nargs="+",
        )

        self.args = parser.parse_args()
        self._setup_logger()
        settings = RuntimeSettings()
        loaders = []
        threads = []
        try:
            for _cluster in self.args.clusters:
                loader = ClusterJobsLoader(
                    EmulatedCluster(settings, _cluster, self.args.state)
                )
                thread = threading.Thread(target=loader.run)
                loaders.append(loader)
                threads.append(thread)
                thread.start()
            # wait for any thread
            threads[0].join()
        except FireHPCRuntimeError as e:
            logger.critical(str(e))
            sys.exit(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, setting loader stop flag.")
            for loader in loaders:
                loader.stop = True
            logger.info("Waiting for loader threads to stop…")
            for thread in threads:
                thread.join()
            logger.info("Cluster jobs loader is stopped.")

    def _setup_logger(self) -> None:
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
