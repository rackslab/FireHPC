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
from typing import TYPE_CHECKING, Optional
from pathlib import Path
import shutil
import logging

import ansible_runner
import yaml

from .templates import Templater
from .users import UsersDirectory
from .containers import (
    ContainersManager,
    ContainerImage,
    StorageService,
)
from .errors import FireHPCRuntimeError

if TYPE_CHECKING:
    from racksdb import RacksDB
    from .settings import RuntimeSettings
    from .images import OSImagesSources
    from .containers import Container

logger = logging.getLogger(__name__)


@dataclass
class ClusterStatus:
    containers: list[Container]
    users: UsersDirectory

    def _generic(self):
        return {
            "containers": [container.name for container in self.containers],
            "users": self.users._generic(),
        }


class EmulatedCluster:
    def __init__(self, settings: RuntimeSettings, name: str, state: Path):
        self.settings = settings
        self.name = name
        self.state = state

    @property
    def cluster_dir(self) -> Path:
        return self.state / self.name

    @property
    def conf_dir(self) -> Path:
        return self.cluster_dir / "conf"

    @property
    def extravars_path(self) -> Path:
        return self.conf_dir / "custom.yml"

    @property
    def users_directory(self) -> UsersDirectory:
        try:
            with open(self.extravars_path) as fh:
                content = yaml.safe_load(fh)
        except FileNotFoundError:
            raise FireHPCRuntimeError(
                f"Unable to find cluster {self.name} extra variables file "
                f"{self.extravars_path}"
            )
        return UsersDirectory.load(self.name, content["fhpc_users"])

    def deploy(
        self,
        os: str,
        images: OSImagesSources,
        db: RacksDB,
        emulator_mode: bool,
    ) -> None:

        if not self.state.exists():
            logger.debug("Creating state directory %s", self.state)
            self.state.mkdir(parents=True)
        if not self.cluster_dir.exists():
            logger.debug("Creating cluster state directory %s", self.cluster_dir)
            self.cluster_dir.mkdir()

        infrastructure = db.infrastructures[self.name]

        admin_node = infrastructure.nodes.filter(tags=["admin"]).first()
        admin_image = ContainerImage.download(
            self.name,
            images.url(os),
            f"{admin_node.name}.{self.name}",
        )
        if not emulator_mode:
            for node in infrastructure.nodes:
                if "admin" not in node.tags:
                    logger.info(
                        "Cloning admin container image for %s.%s", node.name, self.name
                    )
                    admin_image.clone(f"{node.name}.{self.name}")

        logger.info("Starting cluster storage service %s", self.name)
        storage = StorageService(self.name)
        storage.start()

        manager = ContainersManager(self.name)
        if emulator_mode:
            manager.start([admin_node.name])
        else:
            manager.start([node.name for node in infrastructure.nodes])

    def conf(
        self,
        db: RacksDB,
        reinit: bool = True,
        bootstrap: bool = True,
        custom: Path = None,
        tags: Optional[list[str]] = None,
        emulator_mode: bool = False,
        users_directory: Optional[UsersDirectory] = None,
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
                        "Copying custom variables directory %s in configuration "
                        "directory",
                        orig_custom_path,
                    )
                    shutil.copytree(orig_custom_path, dest_custom_path)

        infrastructure = db.infrastructures[self.name]
        for template in ["ansible.cfg", "hosts"]:
            logger.debug(
                "Generating configuration file %s from template",
                self.conf_dir / template,
            )
            with open(self.conf_dir / template, "w+") as fh:
                fh.write(
                    Templater().frender(
                        self.settings.ansible.path / f"{template}.j2",
                        state=self.cluster_dir,
                        cluster=self.name,
                        infrastructure=infrastructure,
                        emulator_mode=emulator_mode,
                    )
                )

        # variable fhpc_addresses
        containers_addresses = {}
        containers = ContainersManager(self.name).running()
        for container in containers:
            containers_addresses[container.name] = [
                str(address) for address in container.addresses()
            ]
        # variable fhpc_nodes
        nodes = {}
        for tag in ["admin", "login", "compute"]:
            nodes[tag] = [node.name for node in infrastructure.nodes.filter(tags=[tag])]

        # Unless already existing, generate custom.yml file with variables and
        # add option to ansible-playbook command line to load this file as a
        # source of extra variables. The file should not be regenerated every
        # times to make randomly generated data (eg. users) persistent over
        # successive runs.
        if not self.extravars_path.exists():
            if users_directory is None:
                # Generate new random users directory
                logger.info("Generating new random users directory")
                users_directory = UsersDirectory(10, self.name)

            extravars = {
                "fhpc_cluster_state_dir": str(self.cluster_dir),
                "fhpc_cluster": self.name,
                "fhpc_users": users_directory._generic(),
            }
            with open(self.extravars_path, "w+") as fh:
                fh.write(yaml.dump(extravars))

        cmdline = f"{self.settings.ansible.args} --extra-vars @{self.extravars_path}"

        if tags is not None and len(tags):
            cmdline += f" --tags {','.join(tags)}"

        playbooks = ["site"]
        if bootstrap:
            playbooks.insert(0, "bootstrap")

        for playbook in playbooks:
            ansible_runner.run(
                private_data_dir=self.conf_dir,
                playbook=f"{self.settings.ansible.path}/{playbook}.yml",
                cmdline=cmdline,
                extravars={
                    "fhpc_addresses": containers_addresses,
                    "fhpc_nodes": nodes,
                    "fhpc_emulator_mode": emulator_mode,
                },
            )

        for generated_dir in ["artifacts", "env"]:
            generated_path = self.conf_dir / generated_dir
            logger.debug("Removing ansible generated directory %s", generated_path)
            shutil.rmtree(generated_path)

    def clean(self) -> None:
        manager = ContainersManager(self.name)

        manager.stop()

        for image in manager.images():
            logger.info("Removing image %s", image.name)
            image.remove()

        logger.info("Stopping cluster storage service")
        storage = StorageService(self.name)
        storage.stop()

    def start(self) -> None:
        manager = ContainersManager(self.name)
        # Search for the list of available images.
        containers = [image.name for image in manager.images()]
        # Look for the running container and start the other.
        running = [container.name for container in manager.running()]
        manager.start(
            [
                # The name of the cluster must be removed from container name.
                container.rsplit(".", 1)[0]
                for container in containers
                if container not in running
            ]
        )

    def stop(self) -> None:
        manager = ContainersManager(self.name)
        manager.stop()

    def status(self) -> ClusterStatus:
        containers = ContainersManager(self.name).running()
        return ClusterStatus(containers, self.users_directory)
