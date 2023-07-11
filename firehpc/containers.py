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

from dasbus.connection import SystemMessageBus


@dataclass
class RunningContainer:
    name: str
    path: Path


class ContainersManager:
    def __init__(self, zone: str) -> ContainersManager:
        self.zone = zone

    def running(self):
        bus = SystemMessageBus()
        proxy = bus.get_proxy(
            "org.freedesktop.machine1", "/org/freedesktop/machine1"
        )
        return [
            RunningContainer(machine[0], Path(machine[3]))
            for machine in proxy.ListMachines()
            if machine[0].endswith(f".{self.zone}")
            and machine[1] == 'container'
        ]
