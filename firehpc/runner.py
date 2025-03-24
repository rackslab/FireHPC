# Copyright (c) 2023-2024 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess

from .errors import FireHPCRuntimeError


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    """Run command and optionally check exit code."""
    try:
        return subprocess.run(cmd, check=check)
    except subprocess.CalledProcessError as e:
        raise FireHPCRuntimeError(f"error: {str(e)}")
