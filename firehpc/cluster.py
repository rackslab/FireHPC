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
import subprocess
from io import StringIO
import shutil
import time
import logging

import ansible_runner

from .templates import Templater

logger = logging.getLogger(__name__)

OS_URL = {
    'debian11': 'https://hub.nspawn.org/storage/debian/bullseye/raw/image.raw.xz',
    'rocky8': 'https://hub.nspawn.org/storage/centos/8/raw/image.raw.xz',
}


@dataclass
class EmulatedCluster:
    settings: RuntimeSettings
    zone: str
    os: str
    state: Path

    @property
    def zone_dir(self) -> Path:
        return self.state / self.zone

    @property
    def home_dir(self) -> Path:
        return self.zone_dir / 'home'

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
        if not self.home_dir.exists():
            logger.debug("Creating zone home directory %s", self.home_dir)
            self.home_dir.mkdir()

        cmd = ['machinectl', 'pull-raw', OS_URL[self.os], f"admin.{self.zone}"]
        subprocess.run(cmd)
        for host in ['login', 'cn1', 'cn2']:
            logger.info(
                "Cloning admin container image for %s.%s", host, self.zone
            )
            cmd = [
                'machinectl',
                'clone',
                f"admin.{self.zone}",
                f"{host}.{self.zone}",
            ]
            subprocess.run(cmd)
        cmd = ['machinectl', 'list-images']
        subprocess.run(cmd)
        for host in ['admin', 'login', 'cn1', 'cn2']:
            logger.info("Starting container %s.%s", host, self.zone)
            cmd = [
                'systemctl',
                'start',
                f"firehpc-container@{self.zone}:{host}.service",
            ]
            subprocess.run(cmd)

        if self.conf_dir.exists():
            logger.debug(
                "Removing existing configuration directory %s", self.conf_dir
            )
            shutil.rmtree(self.conf_dir)

        self.conf_dir.mkdir()

        for template in ['ansible.cfg', 'hosts']:
            logger.debug("Generating configuration file %s from template", self.conf_dir / template)
            with open(self.conf_dir / template, 'w+') as fh:
                fh.write(
                    Templater().frender(
                        self.settings.ansible.path / f"{template}.j2",
                        state=self.zone_dir,
                        zone=self.zone,
                    )
                )

        for subconf_dir in ['group_vars', 'roles', 'playbooks']:
            dest = self.settings.ansible.path / subconf_dir
            source = self.conf_dir / subconf_dir
            logger.debug(
                "Symlinking configuration directory %s →  %s",
                source,
                dest,
            )
            source.symlink_to(dest)

        ansible_extravars = {
            'fhpc_zone_state_dir': str(self.state / self.zone),
            'fhpc_zone': self.zone,
        }

        for playbook in ['bootstrap', 'site']:
            ansible_runner.run(
                private_data_dir=self.conf_dir,
                playbook=f"playbooks/{playbook}.yml",
                extravars=ansible_extravars,
                cmdline=self.settings.ansible.args,
            )

        for generated_dir in ['artifacts', 'env']:
            generated_path = self.conf_dir / generated_dir
            logger.debug(
                "Removing ansible generated directory %s", generated_path
            )
            shutil.rmtree(generated_path)

    def clean(self) -> None:
        for host in ['admin', 'login', 'cn1', 'cn2']:
            logger.info("Powering off container %s.%s", host, self.zone)
            cmd = [
                'machinectl',
                'poweroff',
                f"{host}.{self.zone}",
            ]
            subprocess.run(cmd)

        logger.info("Waiting for containers to power off")
        time.sleep(5.)

        logger.info("Removing container images")
        for host in ['admin', 'login', 'cn1', 'cn2']:
            cmd = [
                'machinectl',
                'remove',
                f"{host}.{self.zone}",
            ]
            subprocess.run(cmd)

        if self.home_dir.is_dir():
            logger.info("Remove zone home directory")
            shutil.rmtree(self.home_dir)
