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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Union
import logging
import shlex
import paramiko

if TYPE_CHECKING:
    from .cluster import EmulatedCluster

from .runner import run
from .errors import FireHPCRuntimeError

logger = logging.getLogger(__name__)


@dataclass
class SSHClient:
    cluster: EmulatedCluster
    asbin: bool = True

    def __init__(self, cluster: EmulatedCluster, asbin: bool = True):
        self.cluster = cluster
        self.asbin = asbin
        self.known_hosts = f"{self.cluster.cluster_dir}/ssh/known_hosts"
        self.private_key = f"{self.cluster.cluster_dir}/ssh/id_rsa"
        if not self.asbin:
            self.clients = {}

    def exec(self, args) -> Union[None, tuple[str, str]]:
        if "@" in args[0]:
            (username, hostname) = args[0].split("@")
        else:
            # connect with root user by default
            username = "root"
            hostname = args[0]
        if self.asbin:
            cmd = [
                "ssh",
                "-o",
                f"UserKnownHostsFile={self.known_hosts}",
                "-i",
                self.private_key,
            ]
            cmd += ["-l", username, hostname]
            cmd += args[1:]
            logger.debug("Running SSH command: %s", shlex.join(cmd))
            run(cmd)
        else:
            if args[0] not in self.clients:
                client = paramiko.SSHClient()
                logger.debug("Loading SSH hosts keys from %s", self.known_hosts)
                client.load_host_keys(self.known_hosts)
                logger.debug("Connecting client to %s@%s", username, hostname)
                client.connect(
                    hostname,
                    username=username,
                    key_filename=self.private_key,
                )
                self.clients[args[0]] = client
            else:
                client = self.clients.get(args[0])

            if len(args) < 2:
                raise FireHPCRuntimeError(
                    "Command to execute must be provided in SSHClient.exec in library "
                    "mode"
                )

            cmd = shlex.join(args[1:])
            logger.debug("Running SSH command with library: %s", cmd)
            stdin, stdout, stderr = client.exec_command(cmd)
            return stdout.read(), stderr.read()
