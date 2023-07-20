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
        return self.zone_dir / "conf"

    @property
    def extravars_path(self) -> Path:
        return self.conf_dir / "custom.yml"

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

        for host in ["login", "cn1", "cn2"]:
            logger.info("Cloning admin container image for %s.%s", host, self.zone)
            admin_image.clone(f"{host}.{self.zone}")

        logger.info("Starting zone storage service %s", self.zone)
        storage = StorageService(self.zone)
        storage.start()

        manager.start(["admin", "login", "cn1", "cn2"])

    def conf(
        self, reinit: bool = True, bootstrap: bool = True, custom: Path = None
    ) -> conf:
        if self.conf_dir.exists() and reinit:
            logger.debug("Removing existing configuration directory %s", self.conf_dir)
            shutil.rmtree(self.conf_dir)

        if not self.conf_dir.exists():
            self.conf_dir.mkdir()

        for subdir in ["group_vars", "host_vars"]:
            dest_custom_path = self.conf_dir / subdir
            if dest_custom_path.exists():
                logger.info(
                    "Removing existing custom variable directory %s",
                    dest_custom_path,
                )
                shutil.rmtree(dest_custom_path)

        if custom:
            for subdir in ["group_vars", "host_vars"]:
                orig_custom_path = custom / subdir
                dest_custom_path = self.conf_dir / subdir
                if orig_custom_path.exists():
                    logger.info(
                        "Copying custom variables directory %s in configuration directory",
                        orig_custom_path,
                    )
                    shutil.copytree(orig_custom_path, dest_custom_path)

        for template in ["ansible.cfg", "hosts"]:
            logger.debug(
                "Generating configuration file %s from template",
                self.conf_dir / template,
            )
            with open(self.conf_dir / template, "w+") as fh:
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
        if not self.extravars_path.exists():
            extravars = {
                "fhpc_zone_state_dir": str(self.zone_dir),
                "fhpc_zone": self.zone,
                "fhpc_users": UsersDirectory(10, self.zone).dump(),
            }
            with open(self.extravars_path, "w+") as fh:
                fh.write(yaml.dump(extravars))

        cmdline = f"{self.settings.ansible.args} --extra-vars @{self.extravars_path}"
        playbooks = ["site"]
        if bootstrap:
            playbooks.insert(0, "bootstrap")

        for playbook in playbooks:
            ansible_runner.run(
                private_data_dir=self.conf_dir,
                playbook=f"{self.settings.ansible.path}/{playbook}.yml",
                cmdline=cmdline,
            )

        for generated_dir in ["artifacts", "env"]:
            generated_path = self.conf_dir / generated_dir
            logger.debug("Removing ansible generated directory %s", generated_path)
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

    def status(self) -> None:
        containers = ContainersManager(self.zone).running()
        print("containers:")
        for container in containers:
            print(f"  {container.name} is running")
        with open(self.extravars_path) as fh:
            content = yaml.safe_load(fh)
        users = UsersDirectory.load(self.zone, content["fhpc_users"])
        print("users:")
        for user in users:
            print(f"  {user.login:15s} ({user.firstname} {user.lastname})")
