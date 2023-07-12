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
import shutil
import time
import logging

import ansible_runner
import yaml

from .templates import Templater
from .users import UsersDirectory
from .containers import (
    ContainersManager,
    Container,
    ContainerImage,
    StorageService,
)

logger = logging.getLogger(__name__)


@dataclass
class EmulatedCluster:
    settings: RuntimeSettings
    zone: str
    os: str
    state: Path
    images: OSImagesSources

    @property
    def zone_dir(self) -> Path:
        return self.state / self.zone

    @property
    def conf_dir(self) -> Path:
        return self.zone_dir / 'conf'

    def deploy(self) -> None:

        if not self.state.exists():
            logger.debug("Creating state directory %s", self.state)
            self.state.mkdir(parents=True)
        if not self.zone_dir.exists():
            logger.debug("Creating zone state directory %s", self.zone_dir)
            self.zone_dir.mkdir()

        admin_image = ContainerImage.download(
            self.zone,
            self.images.url(self.os),
            f"admin.{self.zone}",
        )
        manager = ContainersManager(self.zone)

        for host in ['login', 'cn1', 'cn2']:
            logger.info(
                "Cloning admin container image for %s.%s", host, self.zone
            )
            admin_image.clone(f"{host}.{self.zone}")

        images = manager.images()
        for image in images:
            print(f"image: {image.name} size: {image.volume}")

        logger.info("Starting zone storage service %s", self.zone)
        storage = StorageService(self.zone)
        storage.start()

        manager.start(['admin', 'login', 'cn1', 'cn2'])

    def conf(self, reinit=True, bootstrap=True) -> conf:
        if self.conf_dir.exists() and reinit:
            logger.debug(
                "Removing existing configuration directory %s", self.conf_dir
            )
            shutil.rmtree(self.conf_dir)

        if not self.conf_dir.exists():
            self.conf_dir.mkdir()

        for template in ['ansible.cfg', 'hosts']:
            logger.debug(
                "Generating configuration file %s from template",
                self.conf_dir / template,
            )
            with open(self.conf_dir / template, 'w+') as fh:
                fh.write(
                    Templater().frender(
                        self.settings.ansible.path / f"{template}.j2",
                        state=self.zone_dir,
                        zone=self.zone,
                    )
                )

        # Unless already existing, generate custom.yml file with variables and
        # add option to ansible-playbook command line to load this file as a
        # source of extra variables. The file should not be regenerated every
        # times to make randomly generated data (eg. users) persistent over
        # successive runs.
        extravars_path = self.conf_dir / 'custom.yml'
        if not extravars_path.exists():
            extravars = {
                'fhpc_zone_state_dir': str(self.zone_dir),
                'fhpc_zone': self.zone,
                'fhpc_users': UsersDirectory(10, self.zone).dump(),
            }
            with open(extravars_path, 'w+') as fh:
                fh.write(yaml.dump(extravars))

        cmdline = f"{self.settings.ansible.args} --extra-vars @{extravars_path}"
        playbooks = ['site']
        if bootstrap:
            playbooks.insert(0, 'bootstrap')

        for playbook in playbooks:
            ansible_runner.run(
                private_data_dir=self.conf_dir,
                playbook=f"{self.settings.ansible.path}/{playbook}.yml",
                cmdline=cmdline,
            )

        for generated_dir in ['artifacts', 'env']:
            generated_path = self.conf_dir / generated_dir
            logger.debug(
                "Removing ansible generated directory %s", generated_path
            )
            shutil.rmtree(generated_path)

    def clean(self) -> None:
        manager = ContainersManager(self.zone)

        manager.stop()

        for image in manager.images():
            logger.info("Removing image %s", image.name)
            image.remove()

        logger.info("Stopping zone storage service")
        storage = StorageService(self.zone)
        storage.stop()
