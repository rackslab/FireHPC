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

import os
import dataclasses
from pathlib import Path
import shutil
import logging

from .settings import ClusterSettings
from .errors import FireHPCRuntimeError

import yaml

logger = logging.getLogger(__name__)


def default_state_dir():
    """Returns the default path to the user state directory, through
    XDG_STATE_HOME environment variable if it is set."""
    return Path(os.getenv("XDG_STATE_HOME", "~/.local/state")).expanduser() / "firehpc"


@dataclasses.dataclass
class UserState:
    path: Path

    @property
    def clusters(self):
        return self.path / "clusters"

    def create(self):
        if not self.path.exists():
            logger.debug("Creating state directory %s", self.path)
            self.path.mkdir(parents=True)
        if not self.clusters.exists():
            logger.debug("Creating clusters state directory %s", self.clusters)
            self.clusters.mkdir()


@dataclasses.dataclass
class ClusterState:
    user_state: UserState
    cluster: str

    @property
    def path(self):
        return self.user_state.clusters / self.cluster

    @property
    def conf(self) -> Path:
        return self.path / "conf"

    @property
    def settings(self) -> Path:
        return self.path / "settings.yml"

    @property
    def extravars(self) -> Path:
        return self.conf / "custom.yml"

    def exists(self):
        return self.path.exists()

    def create(self):
        # ensure users state and clusters directories are created
        self.user_state.create()

        if not self.path.exists():
            logger.debug("Creating cluster state directory %s", self.path)
            self.path.mkdir()

    def clean(self):
        if self.path.exists():
            logger.info("Removing existing cluster state directory %s", self.path)
            shutil.rmtree(self.path)

    def conf_create(self):
        if not self.conf.exists():
            logger.debug("Creating cluster configuration directory %s", self.conf)
            self.conf.mkdir()

    def conf_clean(self):
        if self.conf.exists():
            logger.debug("Removing existing configuration directory %s", self.conf)
            shutil.rmtree(self.conf)

    def save(self, settings: ClusterSettings) -> None:
        """Save cluster settings."""
        with open(self.settings, "w+") as fh:
            logger.info("Saving cluster settings into file %s", self.settings)
            fh.write(yaml.dump(settings.serialize()))

    def load(self):
        """Load cluster settings."""
        if not self.settings.exists():
            raise FireHPCRuntimeError(
                f"Unable to find cluster settings file {self.settings}"
            )
        try:
            with open(self.settings) as fh:
                logger.debug("Loading cluster settings from file %s", self.settings)
                return ClusterSettings.deserialize(yaml.safe_load(fh.read()))
        except KeyError as err:
            raise FireHPCRuntimeError(
                f"Unable to load cluster settings: {err}"
            ) from err
