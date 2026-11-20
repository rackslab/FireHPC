# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Base class of machine providers.

A provider is a technology that manages the machines (containers or virtual machines)
of emulated clusters and their images. A provider only manages the system where it
runs. Hosts (see firehpc.hosts) run providers either in the firehpc process or
through firehpc-agent on remote hosts."""

from __future__ import annotations
import abc


class MachineProvider(abc.ABC):
    """Manage the machines of a cluster. All methods accept and return plain
    serializable values (strings, booleans, lists and dicts) so they can be called
    transparently through firehpc-agent."""

    # Name of the provider in registry
    NAME: str = ""

    # Methods that can be called through firehpc-agent
    METHODS = (
        "namespace",
        "image_exists",
        "import_image",
        "remove_image",
        "create_machine",
        "remove_machine",
        "prepare_cluster",
        "release_cluster",
        "start",
        "stop",
        "running",
        "addresses",
        "machines",
    )

    # Ansible connection plugin used to bootstrap machines before SSH is available
    BOOTSTRAP_CONNECTION: str = ""

    def __init__(self, cluster: str):
        self.cluster = cluster

    @abc.abstractmethod
    def namespace(self) -> str:
        """Return the namespace of machines names, unique per user on the host."""

    @abc.abstractmethod
    def image_exists(self, name: str) -> bool:
        """Return True if the base image is available."""

    @abc.abstractmethod
    def import_image(self, url: str, name: str) -> None:
        """Import base image from URL."""

    @abc.abstractmethod
    def remove_image(self, name: str) -> None:
        """Remove base image."""

    @abc.abstractmethod
    def create_machine(self, base: str, name: str) -> None:
        """Create cluster machine from base image."""

    @abc.abstractmethod
    def remove_machine(self, name: str) -> None:
        """Remove cluster machine."""

    @abc.abstractmethod
    def prepare_cluster(self) -> None:
        """Prepare resources shared by cluster machines (eg. storage)."""

    @abc.abstractmethod
    def release_cluster(self) -> None:
        """Release resources shared by cluster machines."""

    @abc.abstractmethod
    def start(self, names: list[str]) -> None:
        """Start the given machines and wait for them to be running."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop all running machines of the cluster."""

    @abc.abstractmethod
    def running(self) -> list[str]:
        """Return the names of running machines of the cluster."""

    @abc.abstractmethod
    def addresses(self) -> dict[str, list[str]]:
        """Return the network addresses of running machines of the cluster, indexed
        by machine name."""

    @abc.abstractmethod
    def machines(self) -> list[str]:
        """Return the names of all cluster machines, running or not."""
