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
            "cluster",
            help="Cluster to run usage emulation.",
        )

        self.args = parser.parse_args()
        self._setup_logger()
        self.settings = RuntimeSettings()
        try:
            self.cluster = EmulatedCluster(
                self.settings, self.args.cluster, self.args.state
            )
            self.ssh = SSHClient(self.cluster, asbin=False)
            self._run_emulation()
        except FireHPCRuntimeError as e:
            logger.critical(str(e))
            sys.exit(1)
        except KeyboardInterrupt:
            logger.info("Stopping emulation")

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

    def _run_emulation(self) -> None:
        status = self.cluster.status()

        nodes = self._get_nodes()
        logger.info("Found nodes: %s", nodes)
        partitions = self._get_partitions()
        logger.info("Found partitions: %s", partitions)
        qos = self._get_qos()
        logger.info("Found QOS: %s", qos)

        while True:
            pending_jobs = self._get_pending_jobs()
            if len(pending_jobs) >= len(nodes) * 10:
                logger.debug("Waiting for pending jobs to run…")
                time.sleep(5)
            else:
                nb_submit = len(nodes) * 10 - len(pending_jobs)
                logger.info("%s new jobs to submit", nb_submit)
                while nb_submit:
                    user = random.choice(status.users.db)
                    self._launch_job(user, qos[0], partitions[0])
                    nb_submit -= 1

    def _get_nodes(self) -> list[str]:
        stdout, stderr = self.ssh.exec(
            [f"admin.{self.args.cluster}", "scontrol", "show", "nodes", "--json"]
        )
        return [node["name"] for node in json.loads(stdout)["nodes"]]

    def _get_partitions(self) -> list[str]:
        stdout, stderr = self.ssh.exec(
            [f"admin.{self.args.cluster}", "scontrol", "show", "partitions", "--json"]
        )
        return [partition["name"] for partition in json.loads(stdout)["partitions"]]

    def _get_qos(self) -> list[str]:
        stdout, stderr = self.ssh.exec(
            [f"admin.{self.args.cluster}", "sacctmgr", "show", "qos", "--json"]
        )
        return [qos["name"] for qos in json.loads(stdout)["QOS"]]

    def _get_pending_jobs(self):
        stdout, stderr = self.ssh.exec(
            [f"admin.{self.args.cluster}", "squeue", "--state", "pending", "--json"]
        )
        return [
            job["job_id"]
            for job in json.loads(stdout)["jobs"]
            if job["job_state"] == "PENDING"
        ]

    def _launch_job(self, user: UserEntry, qos: str, partition: str) -> None:
        logger.info(
            "Submitting job for user %s on partition %s with QOS %s",
            user.login,
            qos,
            partition,
        )
        self.ssh.exec(
            [
                f"{user.login}@login.{self.args.cluster}",
                "sbatch",
                "-q",
                qos,
                "-p",
                partition,
                "--wrap",
                "/usr/bin/sleep 360",
            ]
        )
