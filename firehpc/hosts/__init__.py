# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Hosts where machine providers run and cluster machines live, either the local
host or a remote host reached through SSH."""

from __future__ import annotations
import abc
import atexit
import typing as t

if t.TYPE_CHECKING:
    import socket

    from ..providers.base import MachineProvider


class Host(abc.ABC):
    """Host of cluster machines."""

    # Remote host destination, None on local host
    remote: t.Optional[str] = None

    @property
    def is_remote(self) -> bool:
        return self.remote is not None

    @property
    @abc.abstractmethod
    def label(self) -> str:
        """Human readable name of the host."""

    @abc.abstractmethod
    def provider(self, kind: str, cluster: str) -> MachineProvider:
        """Return machine provider of the given kind for cluster on this host."""

    @abc.abstractmethod
    def open_tcp(self, host: str, port: int) -> socket.socket:
        """Open TCP connection to a machine. The machine name is resolved on this
        host. The returned object is accepted as socket by Paramiko."""

    def ssh_proxy_command(self) -> t.Optional[str]:
        """Return OpenSSH ProxyCommand to reach machines on this host, or None when
        not required."""
        return None

    def ssh_proxy_args(self) -> list[str]:
        """Return OpenSSH client arguments to reach machines on this host."""
        proxy_command = self.ssh_proxy_command()
        if proxy_command is None:
            return []
        return ["-o", f"ProxyCommand={proxy_command}"]

    def close(self) -> None:
        """Release resources associated to this host."""


_hosts: dict[t.Optional[str], Host] = {}


def get_host(remote: t.Optional[str] = None) -> Host:
    """Return the host for the given remote destination, or the local host when
    remote is None or empty. Hosts are cached so that connections to remote hosts
    are shared."""
    remote = remote or None
    if remote not in _hosts:
        if remote is None:
            from .local import LocalHost

            _hosts[remote] = LocalHost()
        else:
            from .remote import RemoteHost

            _hosts[remote] = RemoteHost(remote)
    return _hosts[remote]


@atexit.register
def close_hosts() -> None:
    for host in _hosts.values():
        host.close()
    _hosts.clear()
