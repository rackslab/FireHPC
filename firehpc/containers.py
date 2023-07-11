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
from datetime import datetime
import signal
import threading
import time
import logging

from dasbus.connection import SystemMessageBus
from dasbus.loop import EventLoop

from .errors import FireHPCRuntimeError

logger = logging.getLogger(__name__)


class Singleton(type):
    __instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in Singleton.__instances:
            Singleton.__instances[cls] = super(Singleton, cls).__call__(
                *args, **kwargs
            )
        return Singleton.__instances[cls]


class DBus(metaclass=Singleton):
    def __init__(self) -> DBus:
        self.bus = SystemMessageBus()

    def proxy(self, interface, path):
        return self.bus.get_proxy(interface, path)


class DBusObject:
    def __init__(self, obj: str):
        self.proxy = DBus().proxy(self.INTERFACE, obj)


class UnitService(DBusObject):
    INTERFACE = "org.freedesktop.systemd1"

    def __init__(self, name: str) -> UnitService:
        super().__init__("/org/freedesktop/systemd1")
        self.name = name

    def start(self):
        self.proxy.StartUnit(f"{self.name}.service", "fail")

    def stop(self):
        self.proxy.StartUnit(f"{self.name}.service", "fail")


class ContainerService(UnitService):
    def __init__(self, zone, name):
        super().__init__(f"firehpc-container@{zone}:{name}")


class StorageService(UnitService):
    def __init__(self, zone):
        super().__init__(f"firehpc-storage@{zone}")


class ImageImporter(DBusObject):
    INTERFACE = "org.freedesktop.import1"

    def __init__(self, url: str, name: str) -> ImagesImporter:
        super().__init__("/org/freedesktop/import1")
        self.url = url
        self.name = name
        self.terminated_transfer = threading.Event()
        self.loop = EventLoop()
        self.transfer_id = None
        self.error = None

    def _transfer_new_handler(
        self, transfer_id: str, transfer_path: str
    ) -> None:
        logger.debug("transfer started: %s", transfer_id)

    def _transfer_removed_handler(
        self, transfer_id: str, transfer_path: str, result: str
    ) -> None:
        logger.debug(
            "transfer removed: %s %s (%s)", transfer_id, transfer_path, result
        )
        logger.deb = logging.getLogger(__name__)
        if transfer_id == self.transfer_id:
            if result == 'done':
                logger.info("Image %s is successfully imported", self.name)
            else:
                self.error = result
            self.terminated_transfer.set()

    def _waiter(self) -> None:
        self.proxy.TransferNew.connect(self._transfer_new_handler)
        self.proxy.TransferRemoved.connect(self._transfer_removed_handler)
        self.loop.run()

    def transfer(self) -> None:
        logger.debug("Starting waiter thread")
        waiter = threading.Thread(target=self._waiter)
        waiter.start()
        logger.info("Downloading image %s from URL %s", self.name, self.url)
        self.transfer_id = self.proxy.PullRaw(
            self.url, self.name, "signature", False
        )[0]
        logger.debug("Waiting for transfer to terminate…")
        self.terminated_transfer.wait()
        self.loop.quit()
        if self.error is not None:
            raise FireHPCRuntimeError(
                f"Transfer of image {self.name} has failed: {self.error}"
            )


class Container(DBusObject):
    INTERFACE = "org.freedesktop.machine1"

    def __init__(self, name: str, path: str) -> Container:
        super().__init__(path)
        self.name = name

    def poweroff(self) -> None:
        # Mimic behaviour of machinectl poweroff that send SIGRTMIN+4 to system
        # manager (1st process) in container to trigger clean poweroff.
        self.proxy.Kill("leader", signal.SIGRTMIN + 4)

    @staticmethod
    def start(zone, name):
        service = ContainerService(zone, name)
        service.start()
        # Slightly wait between each container invocation for network bridge
        # setting to be ready and avoid IP address being sequentially
        # flushed by the next container.
        time.sleep(1.0)
        return ContainersManager(zone).container(name)

    @classmethod
    def from_machine(cls, machine) -> Container:
        return cls(machine[0], machine[3])

    @classmethod
    def from_machine_path(cls, path) -> Container:
        obj = DBus().proxy(cls.INTERFACE, path)
        return cls(
            obj.Name,
            path,
        )


class ContainerImage(DBusObject):
    INTERFACE = "org.freedesktop.machine1"

    def __init__(
        self,
        name: str,
        creation: int,
        modification: int,
        volume: int,
        path: str,
    ):
        super().__init__(path)
        self.name = name
        self.creation = datetime.utcfromtimestamp(creation / 10 ** 6)
        self.modification = datetime.utcfromtimestamp(modification / 10 ** 6)
        self.volume = volume

    def remove(self) -> None:
        self.proxy.Remove()

    def clone(self, target) -> None:
        self.proxy.Clone(target, False)

    @classmethod
    def from_machine_image(cls, image) -> ContainerImage:
        return cls(
            image[0],
            image[3],
            image[4],
            image[5],
            image[6],
        )

    @classmethod
    def from_machine_image_path(cls, path: str) -> ContainerImage:
        obj = DBus().proxy(cls.INTERFACE, path)
        return cls(
            obj.Name,
            obj.CreationTimestamp,
            obj.CreationTimestamp,
            obj.Usage,
            path,
        )

    @staticmethod
    def download(zone: str, url: str, name: str) -> ContainerImage:
        importer = ImageImporter(url, name)
        importer.transfer()
        return ContainersManager(zone).image(name)


class ContainersManager(DBusObject):
    INTERFACE = "org.freedesktop.machine1"

    def __init__(self, zone: str) -> ContainersManager:
        super().__init__("/org/freedesktop/machine1")
        self.zone = zone

    def running(self) -> list:
        return [
            Container.from_machine(machine)
            for machine in self.proxy.ListMachines()
            if machine[0].endswith(f".{self.zone}")
            and machine[1] == 'container'
        ]

    def container(self, name) -> Container:
        return Container.from_machine_path(
            self.proxy.GetMachine(f"{name}.{self.zone}")
        )

    def images(self) -> list:
        return [
            ContainerImage.from_machine_image(image)
            for image in self.proxy.ListImages()
            if image[0].endswith(f".{self.zone}")
        ]

    def image(self, name) -> ContainerImage:
        return ContainerImage.from_machine_image_path(self.proxy.GetImage(name))
