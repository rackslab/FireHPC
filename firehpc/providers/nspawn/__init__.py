# Copyright (c) 2023-2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Machine provider with systemd-nspawn containers, managed through
systemd-{machined,importd} and systemd DBus interfaces."""

from __future__ import annotations
import logging
import typing as t

from ..base import MachineProvider
from .dbus import BaseImage, ContainersManager

logger = logging.getLogger(__name__)


class NspawnProvider(MachineProvider):
    NAME = "nspawn"
    BOOTSTRAP_CONNECTION = "machinectl"

    def __init__(self, cluster: str):
        super().__init__(cluster)
        self.manager = ContainersManager(cluster)

    @classmethod
    def bootstrap_vars(cls, helper: t.Optional[list[str]]) -> dict[str, t.Any]:
        # The machinectl connection plugin runs machinectl on the host of
        # machines through the helper command.
        if not helper:
            return {}
        return {"ansible_machinectl_remote_helper": helper}

    def namespace(self) -> str:
        return self.manager.namespace

    def image_exists(self, name: str) -> bool:
        return self.manager.image_exists(name)

    def import_image(self, url: str, name: str) -> None:
        self.manager.download(url, name)

    def remove_image(self, name: str) -> None:
        logger.info("Removing image %s", name)
        BaseImage.from_machine_image_path(self.manager.proxy.GetImage(name)).remove()

    def create_machine(self, base: str, name: str) -> None:
        self.manager.clone_base(self.manager.base_image(base), name)

    def remove_machine(self, name: str) -> None:
        self.remove_image(f"{name}.{self.cluster}.{self.manager.namespace}")

    def prepare_cluster(self) -> None:
        # Start storage service that provides cluster shared home directories.
        self.manager.storage().start()

    def release_cluster(self) -> None:
        self.manager.storage().stop()

    def start(self, names: list[str]) -> None:
        self.manager.start(names)

    def stop(self) -> None:
        self.manager.stop()

    def running(self) -> list[str]:
        return [container.name for container in self.manager.running()]

    def addresses(self) -> dict[str, list[str]]:
        logger.info("Waiting for IP addresses of containers…")
        return {
            container.name: [str(address) for address in container.addresses()]
            for container in self.manager.running()
        }

    def machines(self) -> list[str]:
        # Remove .<cluster>.<namespace> suffix from images names.
        return [image.name.split(".", 1)[0] for image in self.manager.cluster_images()]
