# Copyright (c) 2023-2025 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
from pathlib import Path
import shutil
import os
import logging

import ansible_runner
import yaml

from .templates import Templater
from .users import UsersDirectory
from .hosts import Host, get_host
from .providers import DEFAULT_PROVIDER, provider_class
from .errors import FireHPCRuntimeError
from .settings import ClusterSettings
from .state import ClusterState, UserState
from .environments import DeploymentEnvironment

if TYPE_CHECKING:
    from racksdb import RacksDB
    from .settings import RuntimeSettings

logger = logging.getLogger(__name__)


def clusters_list(state: Path):
    """Return list of cluster names present in state directory."""
    # Directories without settings only contain secrets kept from a cleaned
    # cluster, they are not listed.
    return [
        path.name
        for path in UserState(state).clusters.glob("*")
        if ClusterState(UserState(state), path.name).settings.exists()
    ]


@dataclass
class ClusterStatus:
    containers: list[str]
    directory: UsersDirectory
    settings: ClusterSettings

    def _generic(self):
        return {
            "containers": self.containers,
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
        cluster_settings: Optional[ClusterSettings] = None,
        remote: Optional[str] = None,
    ):
        self.runtime_settings = runtime_settings
        self.name = name
        self.state = state
        self.cluster_settings = cluster_settings
        # Remote host from cluster settings has precedence over remote argument.
        if cluster_settings is not None:
            remote = cluster_settings.remote
        self.remote = remote or None
        self.provider_kind = DEFAULT_PROVIDER
        self._provider = None
        self._namespace = None

    @property
    def host(self) -> Host:
        return get_host(self.remote)

    @property
    def provider(self):
        """Machine provider of the cluster, running on cluster host."""
        if self._provider is None:
            self._provider = self.host.provider(self.provider_kind, self.name)
        return self._provider

    @property
    def namespace(self) -> str:
        """Namespace of cluster machines names."""
        if self._namespace is None:
            self._namespace = self.provider.namespace()
        return self._namespace

    def check_host(self) -> None:
        """Check the cluster host is reachable and its machine provider is available,
        by retrieving the namespace of machines names."""
        logger.debug("Checking machine provider on %s", self.host.label)
        self.namespace

    @staticmethod
    def _emulator_container_names(infrastructure):
        """Return every admin and login node name, plus the compute container.

        The compute container is always named "compute". Compute nodes declared
        in RacksDB are virtual slurmd instances on that container.
        """
        names = []
        seen = set()
        for tag in ("admin", "login"):
            for node in infrastructure.nodes.filter(tags=[tag]):
                if node.name not in seen:
                    names.append(node.name)
                    seen.add(node.name)
        if "compute" not in seen:
            names.append("compute")
        return names

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
        url: str,
        update_os_image: bool,
        db: RacksDB,
    ) -> None:
        infrastructure = db.infrastructures[self.name]

        provider = self.provider

        base_image_name = os.path.basename(url).split(".")[0]

        if self.host.is_remote:
            logger.info(
                "Deploying cluster %s on remote host %s", self.name, self.remote
            )

        # Check if base image is already present. If not or update_os_image is
        # True, download it. Otherwise, just use it in place.
        if not provider.image_exists(name=base_image_name):
            logger.info("Base image %s must be imported", base_image_name)
            provider.import_image(url=url, name=base_image_name)
        else:
            logger.info("Base image %s is already imported", base_image_name)
            if update_os_image:
                logger.info(
                    "Base image %s must be updated, removing it", base_image_name
                )
                provider.remove_image(name=base_image_name)
                provider.import_image(url=url, name=base_image_name)

        # Emulator mode starts every admin and login node, and a container named
        # compute. RacksDB compute names stay virtual slurmd instances.
        if self.cluster_settings.slurm_emulator:
            names = self._emulator_container_names(infrastructure)
        else:
            names = [node.name for node in infrastructure.nodes]

        for name in names:
            logger.info("Cloning base image for %s.%s", name, self.name)
            provider.create_machine(base=base_image_name, name=name)

        logger.info("Preparing cluster %s shared resources", self.name)
        provider.prepare_cluster()

        provider.start(names=names)

    def conf(
        self,
        db: RacksDB,
        playbooks: list[str],
        reinit: bool = True,
        tags: Optional[list[str]] = None,
        skip_tags: Optional[list[str]] = None,
        users_directory: Optional[UsersDirectory] = None,
        ansible_opts: Optional[list[str]] = None,
        users: int = 10,
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

        namespace = self.namespace

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
                        namespace=namespace,
                        infrastructure=infrastructure,
                        emulator_mode=self.cluster_settings.slurm_emulator,
                        proxy_command=self.host.ssh_proxy_command(),
                    )
                )

        # variable fhpc_addresses
        containers_addresses = self.provider.addresses()

        # variable fhpc_nodes, a dict where nodes are first grouped by tag,
        # then grouped by node type.
        nodes = {}

        def node_type_gpus(node_type):
            result = {}
            if not hasattr(node_type, "gpu"):
                return result
            for gpu in node_type.gpu:
                if gpu.model not in result:
                    result[gpu.model] = 0
                result[gpu.model] += 1
            return result

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
                    "gpus": node_type_gpus(node.type),
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
                users_directory = UsersDirectory(users, self.name)

            extravars = {
                "fhpc_cluster_state_dir": str(self.state.path),
                "fhpc_cluster": self.name,
                "fhpc_namespace": namespace,
                "fhpc_users": users_directory._users_generic(),
                "fhpc_groups": users_directory._groups_generic(),
            }
            with open(self.state.extravars, "w+") as fh:
                fh.write(yaml.dump(extravars))

        cmdline = (
            f"{self.runtime_settings.ansible.args} --extra-vars @{self.state.extravars}"
        )

        if ansible_opts is not None and len(ansible_opts):
            cmdline += f" {' '.join(ansible_opts)}"

        if tags is not None and len(tags):
            cmdline += f" --tags {','.join(tags)}"

        if skip_tags is not None and len(skip_tags):
            cmdline += f" --skip-tags {','.join(skip_tags)}"

        environment = DeploymentEnvironment(
            self.state.user_state,
            self.runtime_settings,
            self.cluster_settings.environment,
        )

        if not environment.exists():
            raise FireHPCRuntimeError(
                f"Unable to find environment {environment.name}, bootstrap first?"
            )

        provider = provider_class(self.provider_kind)

        for playbook in playbooks:
            # Prepend deployment environment bin folder in $PATH so that
            # ansible-runnner will execute ansible-playbook in that folder instead of
            # the one in system paths.
            logger.debug("Adding %s in PATH", environment.bin)
            old_path = os.environ["PATH"]
            os.environ["PATH"] = f"{environment.bin}:{old_path}"

            # Run ansible-playbook
            runner = ansible_runner.run(
                private_data_dir=self.state.conf,
                playbook=f"{self.runtime_settings.ansible.path}/{playbook}.yml",
                cmdline=cmdline,
                extravars={
                    "fhpc_addresses": containers_addresses,
                    "fhpc_db": str(Path.cwd() / db._loader.path),
                    "fhpc_emulator_mode": self.cluster_settings.slurm_emulator,
                    "fhpc_nodes": nodes,
                    "fhpc_bootstrap_connection": provider.BOOTSTRAP_CONNECTION,
                    **provider.bootstrap_vars(self.host.helper_command()),
                },
            )
            # Raise exception on playbook failure
            if runner.rc:
                raise FireHPCRuntimeError(
                    f"Error while running ansible playbook {playbook}"
                )

            # Restore $PATH
            os.environ["PATH"] = old_path

        for generated_dir in ["artifacts", "env"]:
            generated_path = self.state.conf / generated_dir
            logger.debug("Removing ansible generated directory %s", generated_path)
            shutil.rmtree(generated_path)

    def clean(self) -> None:
        provider = self.provider

        provider.stop()

        for machine in provider.machines():
            provider.remove_machine(name=machine)

        logger.info("Releasing cluster %s shared resources", self.name)
        provider.release_cluster()

        # Remove cluster settings and configuration, keep secrets for next
        # deployment.
        self.state.clean()

    def clean_secrets(self) -> None:
        """Remove cluster secrets with the whole cluster state directory."""
        self.state.clean_secrets()

    def start(self) -> None:
        provider = self.provider

        logger.info("Preparing cluster %s shared resources", self.name)
        provider.prepare_cluster()

        # Look for the running machines and start the other.
        running = provider.running()
        provider.start(
            names=[machine for machine in provider.machines() if machine not in running]
        )

    def stop(self) -> None:
        self.provider.stop()

    def status(self) -> ClusterStatus:
        return ClusterStatus(
            self.provider.running(),
            self.users_directory,
            self.cluster_settings,
        )
