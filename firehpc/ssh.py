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
from typing import TYPE_CHECKING, Union
import logging
import shlex
import socket

import paramiko

if TYPE_CHECKING:
    from .cluster import EmulatedCluster

from .runner import run
from .containers import ContainersManager
from .errors import FireHPCRuntimeError

logger = logging.getLogger(__name__)


class SSHClient:
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
        # When dot is absent from hostname, consider it is the cluster name. In this
        # case, connect to admin host of this cluster by default.
        if "." not in hostname:
            hostname = "admin." + hostname
        # append container namespace to hostname
        hostname += f".{ContainersManager(self.cluster).namespace}"
        if self.asbin:
            return self._exec_bin(username, hostname, args[1:])
        else:
            return self._exec_lib(username, hostname, args[1:])

    def _exec_bin(self, username, hostname, cmd):
        _cmd = [
            "ssh",
            "-o",
            f"UserKnownHostsFile={self.known_hosts}",
            "-i",
            self.private_key,
        ]
        _cmd += [
            "-l",
            username,
            hostname,
        ]
        _cmd += cmd
        logger.debug("Running SSH command: %s", shlex.join(_cmd))
        run(_cmd)

    def _exec_lib(self, username, hostname, cmd):
        retries = 0
        max_retries = 3
        client_key = f"{username}@{hostname}"
        while retries < max_retries:
            try:
                if client_key not in self.clients:
                    client = paramiko.SSHClient()
                    logger.debug("Loading SSH hosts keys from %s", self.known_hosts)
                    client.load_host_keys(self.known_hosts)
                    logger.debug("Connecting client to %s@%s", username, hostname)
                    client.connect(
                        hostname,
                        username=username,
                        key_filename=self.private_key,
                    )
                    self.clients[client_key] = client
                else:
                    client = self.clients.get(client_key)

                if not len(cmd):
                    raise FireHPCRuntimeError(
                        "Command to execute must be provided in SSHClient.exec in "
                        "library mode"
                    )

                _cmd = shlex.join(cmd)
                logger.debug("Running SSH command with library: %s", _cmd)
                stdin, stdout, stderr = client.exec_command(_cmd)
                return stdout.read(), stderr.read()
            except socket.gaierror as err:
                raise FireHPCRuntimeError(
                    f"Get address information error for host {hostname}: {err}"
                ) from err
            except paramiko.ssh_exception.SSHException as err:
                logger.error("SSH error while running command '%s': %s", _cmd, err)
                logger.info("Retries left: %d", max_retries - retries)
                retries += 1
                del self.clients[client_key]

        raise FireHPCRuntimeError(
            f"Unable to run SSH command '{_cmd}' after {max_retries} retries"
        )
