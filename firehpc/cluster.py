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
from .containers import ContainersManager
from .errors import FireHPCRuntimeError
from .settings import ClusterSettings
from .state import ClusterState

if TYPE_CHECKING:
    from racksdb import RacksDB
    from .settings import RuntimeSettings
    from .images import OSImagesSources
    from .containers import Container

logger = logging.getLogger(__name__)


def clusters_list(state: Path):
    """Return list of cluster names present in state directory."""
    return [path.name for path in state.glob("*")]


@dataclass
class ClusterStatus:
    containers: list[Container]
    directory: UsersDirectory
    settings: ClusterSettings

    def _generic(self):
        return {
            "containers": [container.name for container in self.containers],
            "users": self.directory._users_generic(),
            "settings": self.settings.serialize(),
            "groups": self.directory._groups_generic(),
        }


class EmulatedCluster:
    def __init__(
        self,
        runtime_settings: RuntimeSettings,
        name: str,
        state: ClusterState,
        cluster_settings: ClusterSettings,
    ):
        self.runtime_settings = runtime_settings
        self.name = name
        self.state = state
        self.cluster_settings = cluster_settings

    @property
    def users_directory(self) -> UsersDirectory:
        try:
            with open(self.state.extravars) as fh:
                content = yaml.safe_load(fh)
        except FileNotFoundError:
            raise FireHPCRuntimeError(
                f"Unable to find cluster {self.name} extra variables file "
                f"{self.state.extravars}"
            )
        return UsersDirectory.load(
            self.name, content["fhpc_users"], content["fhpc_groups"]
        )

    def deploy(
        self,
        os: str,
        images: OSImagesSources,
        db: RacksDB,
    ) -> None:

        infrastructure = db.infrastructures[self.name]

        manager = ContainersManager(self.name)

        admin_node = infrastructure.nodes.filter(tags=["admin"]).first()
        admin_image = manager.download(
            admin_node.name,
            images.url(os),
        )
        if not self.cluster_settings.slurm_emulator:
            for node in infrastructure.nodes:
                if "admin" not in node.tags:
                    logger.info(
                        "Cloning admin container image for %s.%s", node.name, self.name
                    )
                    admin_image.clone(node.name)

        logger.info("Starting cluster storage service %s", self.name)
        manager.storage().start()

        if self.cluster_settings.slurm_emulator:
            manager.start([admin_node.name])
        else:
            manager.start([node.name for node in infrastructure.nodes])

    def conf(
        self,
        db: RacksDB,
        playbooks: list[str],
        reinit: bool = True,
        tags: Optional[list[str]] = None,
        skip_tags: Optional[list[str]] = None,
        users_directory: Optional[UsersDirectory] = None,
    ) -> conf:

        if reinit:
            self.state.conf_clean()

        self.state.conf_create()

        for subdir in ["group_vars", "host_vars"]:
            dest_custom_path = self.state.conf / subdir
            if dest_custom_path.exists():
                logger.info(
                    "Removing existing custom variable directory %s",
                    dest_custom_path,
                )
                shutil.rmtree(dest_custom_path)

        if self.cluster_settings.custom:
            for subdir in ["group_vars", "host_vars"]:
                orig_custom_path = self.cluster_settings.custom / subdir
                dest_custom_path = self.state.conf / subdir
                if orig_custom_path.exists():
                    logger.info(
                        "Copying custom variables directory %s in configuration "
                        "directory",
                        orig_custom_path,
                    )
                    shutil.copytree(orig_custom_path, dest_custom_path)

        manager = ContainersManager(self.name)

        infrastructure = db.infrastructures[self.name]
        for template in ["ansible.cfg", "hosts"]:
            logger.debug(
                "Generating configuration file %s from template",
                self.state.conf / template,
            )
            with open(self.state.conf / template, "w+") as fh:
                fh.write(
                    Templater().frender(
                        self.runtime_settings.ansible.path / f"{template}.j2",
                        state=self.state.path,
                        cluster=self.name,
                        namespace=manager.namespace,
                        infrastructure=infrastructure,
                        emulator_mode=self.cluster_settings.slurm_emulator,
                    )
                )

        # variable fhpc_addresses
        containers_addresses = {}
        for container in manager.running():
            containers_addresses[container.name] = [
                str(address) for address in container.addresses()
            ]

        # variable fhpc_nodes, a dict where nodes are first grouped by tag,
        # then grouped by node type.
        nodes = {}

        def insert_in_node_type():
            for node_type in nodes[tag]:
                if node_type["type"] == node.type.id:
                    node_type["nodes"].append(node.name)
                    return
            nodes[tag].append(
                {
                    "type": node.type.id,
                    "sockets": node.type.cpu.sockets,
                    "cores": node.type.cpu.cores,
                    "memory": node.type.ram.dimm * (node.type.ram.size // 1024**2),
                    "nodes": [node.name],
                }
            )

        for tag in ["admin", "login", "compute"]:
            if tag not in nodes:
                nodes[tag] = []
            for node in infrastructure.nodes.filter(tags=[tag]):
                insert_in_node_type()

        # Unless already existing, generate custom.yml file with variables and
        # add option to ansible-playbook command line to load this file as a
        # source of extra variables. The file should not be regenerated every
        # times to make randomly generated data (eg. users) persistent over
        # successive runs.
        if not self.state.extravars.exists():
            if users_directory is None:
                # Generate new random users directory
                logger.info("Generating new random users directory")
                users_directory = UsersDirectory(10, self.name)

            extravars = {
                "fhpc_cluster_state_dir": str(self.state.path),
                "fhpc_cluster": self.name,
                "fhpc_namespace": manager.namespace,
                "fhpc_users": users_directory._users_generic(),
                "fhpc_groups": users_directory._groups_generic(),
            }
            with open(self.state.extravars, "w+") as fh:
                fh.write(yaml.dump(extravars))

        cmdline = (
            f"{self.runtime_settings.ansible.args} "
            f"--extra-vars @{self.state.extravars}"
        )

        if tags is not None and len(tags):
            cmdline += f" --tags {','.join(tags)}"

        if skip_tags is not None and len(skip_tags):
            cmdline += f" --skip-tags {','.join(skip_tags)}"

        for playbook in playbooks:
            ansible_runner.run(
                private_data_dir=self.state.conf,
                playbook=f"{self.runtime_settings.ansible.path}/{playbook}.yml",
                cmdline=cmdline,
                extravars={
                    "fhpc_addresses": containers_addresses,
                    "fhpc_db": str(Path.cwd() / db._loader.path),
                    "fhpc_emulator_mode": self.cluster_settings.slurm_emulator,
                    "fhpc_nodes": nodes,
                },
            )

        for generated_dir in ["artifacts", "env"]:
            generated_path = self.state.conf / generated_dir
            logger.debug("Removing ansible generated directory %s", generated_path)
            shutil.rmtree(generated_path)

    def clean(self) -> None:
        manager = ContainersManager(self.name)

        manager.stop()

        for image in manager.images():
            logger.info("Removing image %s", image.name)
            image.remove()

        logger.info("Stopping cluster storage service")
        manager.storage().stop()

        # Remove cluster state directory
        self.state.clean()

    def start(self) -> None:
        manager = ContainersManager(self.name)

        logger.info("Starting cluster storage service %s", self.name)
        manager.storage().start()

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
        ContainersManager(self.name).stop()

    def status(self) -> ClusterStatus:
        return ClusterStatus(
            ContainersManager(self.name).running(),
            self.users_directory,
            self.cluster_settings,
        )
