#!/usr/bin/env python3
#
# Copyright (C) 2025 Rackslab
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

"""
Manage deployment environments.

This is a mean to have multiple version of Ansible, depending on the targeted operating
system. The concept is very similar to Ansible Execution Environments (aka. Ansible EE),
but with simple Python virtual environment rather than podman/docker containers.

This specific implementation is preferred because ansible-builder as this tool is not
widely available in host distributions supported by FireHPC and requires itself a Python
virtual environment to be installed. It has been chosen to manage mutltiple virtual
environments with ansible rather than virtual environment with ansible-builder +
podman/docker containers. This may change in the future when ansible-builder is more
widely available in host distributions supported by FireHPC.
"""

from __future__ import annotations
import dataclasses
import typing as t
import logging

if t.TYPE_CHECKING:
    from .settings import RuntimeSettings
    from .state import UserState

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class DeploymentEnvironment:
    state: UserState
    runtime_settings: RuntimeSettings
    name: str

    @property
    def path(self):
        return self.state.path / "venvs" / self.name

    @property
    def bin(self):
        return self.path / "bin"

    def exists(self):
        return self.path.exists()
