# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
import socket

from . import Host
from ..providers import provider_class
from ..providers.base import MachineProvider


class LocalHost(Host):
    """Local host, where providers run in firehpc process."""

    @property
    def label(self) -> str:
        return "local host"

    def provider(self, kind: str, cluster: str) -> MachineProvider:
        return provider_class(kind)(cluster)

    def open_tcp(self, host: str, port: int) -> socket.socket:
        return socket.create_connection((host, port))
