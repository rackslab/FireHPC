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
import venv
import dataclasses
import typing as t
import logging

import yaml

from .runner import run

if t.TYPE_CHECKING:
    from .settings import RuntimeSettings
    from .state import UserState

logger = logging.getLogger(__name__)


def bootstrap(user_state: UserState, runtime_settings: RuntimeSettings) -> None:
    """Bootstrap deployment environments required for all OS in databases."""
    logger.debug("Loading OS database file %s", runtime_settings.os.db)
    with open(runtime_settings.os.db) as fh:
        db = yaml.safe_load(fh)

    # Retrieve the list of environments
    environments = set()
    for os, value in db.items():
        if value["environment"] not in environments:
            environments.add(value["environment"])

    if not environments:
        logger.warning("No environment to create")
        return

    builder = venv.EnvBuilder(clear=True, with_pip=True)
    for environment in environments:
        env = DeploymentEnvironment(user_state, runtime_settings, environment)
        env.create(builder)
        env.install()

    logger.info("Bootstrap successful")


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

    def create(self, builder):
        logger.info("Creating deployment environment %s", self.name)
        builder.create(self.path)

    def install(self):
        logger.info("Installing requirements in deployment environment %s", self.name)
        run(
            [
                self.bin / "pip",
                "install",
                "--requirement",
                self.runtime_settings.os.requirements / f"{self.name}.txt",
            ],
            check=True,
        )
