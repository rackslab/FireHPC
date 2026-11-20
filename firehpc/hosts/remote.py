# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Remote hosts reached through SSH with Paramiko library. Machine providers run on
remote hosts in firehpc-agent program, started through SSH."""

from __future__ import annotations
import logging
import os
import select
import shlex
import socket
import sys
import typing as t
from pathlib import Path

import paramiko

from . import Host
from ..errors import FireHPCRuntimeError
from ..settings import UserPreferences

if t.TYPE_CHECKING:
    from ..agent.client import AgentProvider, AgentSession

logger = logging.getLogger(__name__)

DEFAULT_SSH_PORT = 22


def parse_destination(
    destination: str,
) -> tuple[t.Optional[str], str, t.Optional[int]]:
    """Parse [USER@]HOST[:PORT] destination and return a 3-tuple with user, host
    and port. User and port are None when not specified. IPv6 addresses must be
    enclosed in brackets when port is specified (eg. [::1]:2222)."""
    if not destination:
        raise FireHPCRuntimeError("Empty remote host destination")
    user = None
    port = None
    if "@" in destination:
        user, destination = destination.rsplit("@", 1)
    if destination.startswith("["):
        host, _, rest = destination[1:].partition("]")
        if rest.startswith(":"):
            port = rest[1:]
        elif rest:
            raise FireHPCRuntimeError(f"Invalid remote host destination {destination}")
    elif destination.count(":") == 1:
        host, port = destination.split(":")
    else:
        host = destination
    if port is not None:
        try:
            port = int(port)
        except ValueError as err:
            raise FireHPCRuntimeError(
                f"Invalid port in remote host destination {destination}"
            ) from err
    if not host:
        raise FireHPCRuntimeError(f"Invalid remote host destination {destination}")
    return user or None, host, port


def default_ssh_config_path() -> Path:
    return Path("~/.ssh/config").expanduser()


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


def relay(
    channel: paramiko.Channel,
    stdin_fd: int,
    stdout_fd: int,
    stderr_fd: t.Optional[int] = None,
) -> None:
    """Relay data between local file descriptors and SSH channel until the channel
    is closed by remote side."""
    stdin_open = True
    while True:
        rlist = [channel]
        if stdin_open:
            rlist.append(stdin_fd)
        readable, _, _ = select.select(rlist, [], [], 1)
        if stdin_open and stdin_fd in readable:
            data = os.read(stdin_fd, 32768)
            if data:
                channel.sendall(data)
            else:
                stdin_open = False
                channel.shutdown_write()
        while channel.recv_stderr_ready():
            data = channel.recv_stderr(32768)
            if stderr_fd is not None:
                _write_all(stderr_fd, data)
        while channel.recv_ready():
            _write_all(stdout_fd, channel.recv(32768))
        if (channel.eof_received or channel.closed) and not (
            channel.recv_ready() or channel.recv_stderr_ready()
        ):
            break


def firehpc_command() -> str:
    """Return the path to the current firehpc command, to be called by external
    programs (eg. ssh, ansible)."""
    if os.path.basename(sys.argv[0]) == "firehpc":
        return os.path.abspath(sys.argv[0])
    return "firehpc"


class RemoteHost(Host):
    """Remote host reached through SSH, with parameters from destination and user
    OpenSSH client configuration file."""

    # Command to start firehpc-agent on remote hosts
    agent_command = UserPreferences.DEFAULT_AGENT

    def __init__(self, destination: str, ssh_config_path: t.Optional[Path] = None):
        self.remote = destination
        self.destination = destination
        user, host, port = parse_destination(destination)
        if ssh_config_path is None:
            ssh_config_path = default_ssh_config_path()
        config = {}
        if ssh_config_path.exists():
            logger.debug("Loading SSH client configuration %s", ssh_config_path)
            config = paramiko.SSHConfig.from_path(str(ssh_config_path)).lookup(host)
        self.hostname = config.get("hostname", host)
        self.user = user or config.get("user")
        self.port = port or int(config.get("port", DEFAULT_SSH_PORT))
        self.key_filenames = config.get("identityfile")
        self.proxy_command = config.get("proxycommand")
        if "proxyjump" in config:
            logger.warning(
                "ProxyJump is not supported for remote host %s, use ProxyCommand "
                "instead in SSH client configuration",
                destination,
            )
        self._client = None
        self._session = None

    @property
    def label(self) -> str:
        return self.destination

    @property
    def client(self) -> paramiko.SSHClient:
        if self._client is None:
            self._client = self._connect()
        return self._client

    @property
    def transport(self) -> paramiko.Transport:
        return self.client.get_transport()

    def _connect(self) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        sock = None
        if self.proxy_command:
            sock = paramiko.ProxyCommand(self.proxy_command)
        logger.debug(
            "Connecting to remote host %s (hostname: %s, port: %d, user: %s)",
            self.destination,
            self.hostname,
            self.port,
            self.user,
        )
        try:
            client.connect(
                self.hostname,
                port=self.port,
                username=self.user,
                key_filename=self.key_filenames,
                sock=sock,
            )
        except paramiko.BadHostKeyException as err:
            raise FireHPCRuntimeError(
                f"Host key of remote host {self.destination} does not match known "
                f"hosts: {err}"
            ) from err
        except paramiko.AuthenticationException as err:
            raise FireHPCRuntimeError(
                f"Unable to authenticate on remote host {self.destination}: {err}"
            ) from err
        except paramiko.SSHException as err:
            # RejectPolicy raises a generic SSHException for unknown hosts.
            raise FireHPCRuntimeError(
                f"SSH error with remote host {self.destination}: {err}. If the remote "
                "host key is unknown, connect once with ssh to add it in known hosts."
            ) from err
        except (OSError, socket.gaierror) as err:
            raise FireHPCRuntimeError(
                f"Unable to connect to remote host {self.destination}: {err}"
            ) from err
        client.get_transport().set_keepalive(30)
        return client

    def exec_stream(self, cmd: str) -> paramiko.Channel:
        """Run command on remote host and return the channel without waiting for
        command to terminate."""
        logger.debug("Running command on remote host %s: %s", self.destination, cmd)
        channel = self.transport.open_session()
        channel.exec_command(cmd)
        return channel

    def exec(self, cmd: str) -> tuple[int, bytes, bytes]:
        """Run command on remote host, wait for its termination and return a 3-tuple
        with its exit status, its standard output and its standard error."""
        channel = self.exec_stream(cmd)
        channel.shutdown_write()
        stdout = channel.makefile("rb").read()
        stderr = channel.makefile_stderr("rb").read()
        return channel.recv_exit_status(), stdout, stderr

    def run(self, cmd: str, stdin_fd: int, stdout_fd: int, stderr_fd: int) -> int:
        """Run command on remote host, relay its standard input, output and error
        with the given local file descriptors and return its exit status."""
        channel = self.exec_stream(cmd)
        relay(channel, stdin_fd, stdout_fd, stderr_fd)
        return channel.recv_exit_status()

    def open_tcp(self, host: str, port: int) -> paramiko.Channel:
        """Open a TCP connection to host and port from the remote host. The host
        name is resolved on the remote host."""
        logger.debug(
            "Opening TCP channel to %s:%d through remote host %s",
            host,
            port,
            self.destination,
        )
        try:
            return self.transport.open_channel(
                "direct-tcpip", (host, port), ("127.0.0.1", 0)
            )
        except paramiko.ChannelException as err:
            raise FireHPCRuntimeError(
                f"Unable to open TCP channel to {host}:{port} through remote host "
                f"{self.destination}: {err}"
            ) from err

    def upload(self, local: str, remote: str) -> None:
        """Copy local file to remote host, with the same permissions."""
        logger.debug("Uploading %s to %s:%s", local, self.destination, remote)
        with self.client.open_sftp() as sftp:
            sftp.put(local, remote)
            sftp.chmod(remote, os.stat(local).st_mode & 0o7777)

    def download(self, remote: str, local: str) -> None:
        """Copy file from remote host to local host."""
        logger.debug("Downloading %s:%s to %s", self.destination, remote, local)
        with self.client.open_sftp() as sftp:
            sftp.get(remote, local)

    @property
    def session(self) -> AgentSession:
        """Session with firehpc-agent on remote host, started on first use."""
        if self._session is None:
            from ..agent.client import AgentSession

            self._session = AgentSession.start(self, self.agent_command)
        return self._session

    def provider(self, kind: str, cluster: str) -> AgentProvider:
        from ..agent.client import AgentProvider

        return AgentProvider(self.session, kind, cluster)

    def ssh_proxy_command(self) -> str:
        return (
            shlex.join([firehpc_command(), "--remote", self.remote, "remote", "proxy"])
            + " %h %p"
        )

    def helper_command(self) -> list[str]:
        return [firehpc_command(), "--remote", self.remote, "remote"]

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None
        if self._client is not None:
            self._client.close()
            self._client = None
