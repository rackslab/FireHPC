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
from pathlib import Path
from datetime import datetime
from functools import cached_property
import signal

from dasbus.connection import SystemMessageBus


@dataclass
class RunningContainer:
    name: str
    path: Path

    @cached_property
    def proxy(self):
        return SystemMessageBus().get_proxy(
            "org.freedesktop.machine1", str(self.path)
        )

    def poweroff(self) -> None:
        # Mimic behaviour of machinectl poweroff that send SIGRTMIN+4 to system
        # manager (1st process) in container to trigger clean poweroff.
        self.proxy.Kill("leader", signal.SIGRTMIN + 4)


@dataclass
class ContainerImage:
    name: str
    creation: datetime
    modification: datetime
    volume: int
    path: Path

    @cached_property
    def proxy(self):
        return SystemMessageBus().get_proxy(
            "org.freedesktop.machine1", str(self.path)
        )

    def remove(self) -> None:
        self.proxy.Remove()


class ContainersManager:
    def __init__(self, zone: str) -> ContainersManager:
        self.zone = zone
        self.proxy = SystemMessageBus().get_proxy(
            "org.freedesktop.machine1", "/org/freedesktop/machine1"
        )

    def running(self) -> list:
        return [
            RunningContainer(machine[0], Path(machine[3]))
            for machine in self.proxy.ListMachines()
            if machine[0].endswith(f".{self.zone}")
            and machine[1] == 'container'
        ]

    def images(self) -> list:
        return [
            ContainerImage(
                image[0],
                datetime.utcfromtimestamp(image[3] / 10 ** 6),
                datetime.utcfromtimestamp(image[4] / 10 ** 6),
                image[5],
                Path(image[6]),
            )
            for image in self.proxy.ListImages()
            if image[0].endswith(f".{self.zone}")
        ]
