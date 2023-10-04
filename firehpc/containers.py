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
import socket
import ipaddress
import logging

from dasbus.connection import SystemMessageBus
from dasbus.loop import EventLoop
from dasbus.error import DBusError

from .errors import FireHPCRuntimeError

logger = logging.getLogger(__name__)


class Singleton(type):
    __instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in Singleton.__instances:
            Singleton.__instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
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

    def __init__(self, url: str, name: str) -> ImageImporter:
        super().__init__("/org/freedesktop/import1")
        self.url = url
        self.name = name
        self.terminated_transfer = threading.Event()
        self.loop = EventLoop()
        self.transfer_id = None
        self.error = None

    def _transfer_new_handler(self, transfer_id: str, transfer_path: str) -> None:
        logger.debug("transfer started: %s", transfer_id)

    def _transfer_removed_handler(
        self, transfer_id: str, transfer_path: str, result: str
    ) -> None:
        logger.debug("transfer removed: %s %s (%s)", transfer_id, transfer_path, result)
        if transfer_id == self.transfer_id:
            if result == "done":
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
        self.transfer_id = self.proxy.PullRaw(self.url, self.name, "signature", False)[
            0
        ]
        logger.debug("Waiting for transfer to terminate…")
        self.terminated_transfer.wait()
        self.loop.quit()
        if self.error is not None:
            raise FireHPCRuntimeError(
                f"Transfer of image {self.name} has failed: {self.error}"
            )


class ClusterStateModifier(DBusObject):
    INTERFACE = "org.freedesktop.machine1"

    def __init__(self, zone: str) -> ClusterStateModifier:
        super().__init__("/org/freedesktop/machine1")
        self.zone = zone
        self.loop = EventLoop()
        self.terminated_start = threading.Event()
        self.terminated_stop = threading.Event()
        self.must_start = []
        self.must_stop = []
        self.locker = threading.Lock()

    def _machine_new_handler(self, machine: str, path: str) -> None:
        logger.debug("machine started: %s", machine)
        self.locker.acquire()
        if machine in self.must_start:
            self.must_start.remove(machine)
        if not len(self.must_start):
            self.terminated_start.set()
        self.locker.release()

    def _machine_removed_handler(self, machine: str, path: str) -> None:
        logger.debug("machine stopped: %s", machine)
        self.locker.acquire()
        if machine in self.must_stop:
            self.must_stop.remove(machine)
        if not len(self.must_stop):
            self.terminated_stop.set()
        self.locker.release()

    def _waiter(self) -> None:
        self.proxy.MachineNew.connect(self._machine_new_handler)
        self.proxy.MachineRemoved.connect(self._machine_removed_handler)
        self.loop.run()

    def start(self, containers: list) -> None:
        self.must_start = [f"{container}.{self.zone}" for container in containers]
        if not len(self.must_start):
            logger.info("No container to start")
            return
        logger.debug("Starting waiter thread")
        waiter = threading.Thread(target=self._waiter)
        waiter.start()
        for container in containers:
            logger.info("Starting container %s.%s", container, self.zone)
            Container.start(self.zone, container)
        logger.info("Waiting for containers to start…")
        self.terminated_start.wait()
        logger.info("All containers are successfully started")
        self.loop.quit()

    def stop(self, containers: list) -> None:
        self.must_stop = [container.name for container in containers]
        if not len(self.must_stop):
            logger.info("No container to stop")
            return
        logger.debug("Starting waiter thread")
        waiter = threading.Thread(target=self._waiter)
        waiter.start()
        for container in containers:
            logger.info("Powering off container %s", container.name)
            container.poweroff()
        logger.info("Waiting for containers to stop…")
        self.terminated_stop.wait()
        logger.info("All containers are successfully stopped")
        self.loop.quit()


class Container(DBusObject):
    INTERFACE = "org.freedesktop.machine1"

    def __init__(self, name: str, path: str) -> Container:
        super().__init__(path)
        self.name = name

    def poweroff(self) -> None:
        # Mimic behaviour of machinectl poweroff that send SIGRTMIN+4 to system
        # manager (1st process) in container to trigger clean poweroff.
        self.proxy.Kill("leader", signal.SIGRTMIN + 4)

    def addresses(self, wait: bool = True) -> list[str]:
        """Return the list of network addresses (ipv4 and ipv6) assigned to the
        container. When wait is True, the method waits until the list of IP addresses is
        not empty."""
        result = []
        # machine1 DBus interface returns a sequence of pairs: the 1st element is the
        # address type and the 2nd element is a tuple with address all bytes as separate
        # integers.
        while True:
            for address in self.proxy.GetAddresses():
                if address[0] == int(socket.AF_INET):
                    # Join all bytes with . to build an IPv4 address
                    result.append(ipaddress.IPv4Address(".".join(map(str, address[1]))))
                elif address[0] == int(socket.AF_INET6):
                    # Join with : all 2 bytes converted a string of hex values
                    result.append(
                        ipaddress.IPv6Address(
                            ":".join(
                                [f"{a:x}{b:x}" for a, b in zip(*[iter(address[1])] * 2)]
                            )
                        )
                    )
                else:
                    logger.error(
                        "Unsupported socket type %d for address of container %s",
                        address[0],
                        self.name,
                    )
            if len(result) or not wait:
                break  # stop main while loop
            else:
                logger.debug(
                    "IP addresses of containers %s are not available, retrying…",
                    self.name,
                )
                time.sleep(1)
        return result

    @staticmethod
    def start(zone, name) -> None:
        service = ContainerService(zone, name)
        service.start()

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

    def remove(self, retries=3) -> None:
        left = retries
        while left:
            try:
                self.proxy.Remove()
            except DBusError as err:
                if str(err) == "Device or resource busy":
                    logger.debug(
                        "Container image (%s) busy, retrying (%d)…",
                        self.name,
                        left,
                    )
                    time.sleep(1)
                    left -= 1
                    continue
                else:
                    raise FireHPCRuntimeError(
                        f"Unable to remove container image {self.name}: {err}"
                    ) from err
            else:
                return
        raise FireHPCRuntimeError(
            f"Unable to remove container image {self.name} after {retries} tries"
        )

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
            if machine[0].endswith(f".{self.zone}") and machine[1] == "container"
        ]

    def container(self, name) -> Container:
        return Container.from_machine_path(self.proxy.GetMachine(f"{name}.{self.zone}"))

    def images(self) -> list:
        return [
            ContainerImage.from_machine_image(image)
            for image in self.proxy.ListImages()
            if image[0].endswith(f".{self.zone}")
        ]

    def image(self, name) -> ContainerImage:
        return ContainerImage.from_machine_image_path(self.proxy.GetImage(name))

    def start(self, containers: list):
        ClusterStateModifier(self.zone).start(containers)

    def stop(self):
        ClusterStateModifier(self.zone).stop(self.running())
