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

from .runner import run


@dataclass
class SSHClient:
    cluster: EmulatedCluster

    def exec(self, args):
        cmd = [
            'ssh',
            '-o',
            f"UserKnownHostsFile={self.cluster.zone_dir}/ssh/known_hosts",
            '-i',
            f"{self.cluster.zone_dir}/ssh/id_rsa",
        ]
        # connect with root user by default
        if '@' not in args[0]:
            cmd += ['-l', 'root']
        cmd += args
        run(cmd)
