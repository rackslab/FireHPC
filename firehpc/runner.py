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

import subprocess

from .errors import FireHPCRuntimeError


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    """Run command and optionally check exit code."""
    try:
        return subprocess.run(cmd, check=check)
    except subprocess.CalledProcessError as e:
        raise FireHPCRuntimeError(f"error: {str(e)}")
