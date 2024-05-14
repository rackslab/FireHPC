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
import os
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
        self.proxy.StopUnit(f"{self.name}.service", "fail")


class ContainerService(UnitService):
    def __init__(self, name, cluster, namespace):
        super().__init__(f"firehpc-container@{cluster}.{namespace}:{name}")


class StorageService(UnitService):
    def __init__(self, cluster, namespace):
        super().__init__(f"firehpc-storage@{cluster}.{namespace}")


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

    def __init__(self, cluster: str, namespace: str) -> ClusterStateModifier:
        super().__init__("/org/freedesktop/machine1")
        self.cluster = cluster
        self.namespace = namespace
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
        self.must_start = [
            f"{container}.{self.cluster}.{self.namespace}" for container in containers
        ]
        if not len(self.must_start):
            logger.info("No container to start")
            return
        logger.debug(
            "Starting waiter thread for containers to start: %s", self.must_start
        )
        waiter = threading.Thread(target=self._waiter)
        waiter.start()
        wait_first = True
        for container in containers:
            logger.info("Starting container %s", container)
            Container.start(container, self.cluster, self.namespace)
            # Wait some time before starting the second container to let systemd-nspawn
            # and systemd-networkd setup cluster private network properly and avoid
            # the following container from erasing everything before completion.
            if wait_first and len(containers) > 1:
                logger.debug("Waiting for network to setup for first container")
                time.sleep(3)
                wait_first = False
        logger.info("Waiting for containers to start…")
        self.terminated_start.wait()
        logger.info("All containers are successfully started")
        self.loop.quit()

    def stop(self, containers: list) -> None:
        self.must_stop = [container.fqdn for container in containers]
        if not len(self.must_stop):
            logger.info("No container to stop")
            return
        logger.debug(
            "Starting waiter thread for containers for containers to stop: %s",
            self.must_stop,
        )
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

    def __init__(self, name: str, cluster: str, namespace: str, path: str) -> Container:
        super().__init__(path)
        self.name = name
        self.cluster = cluster
        self.namespace = namespace

    @property
    def fqdn(self):
        return f"{self.name}.{self.cluster}.{self.namespace}"

    def poweroff(self) -> None:
        # Mimic behaviour of machinectl poweroff that send SIGRTMIN+4 to system
        # manager (1st process) in container to trigger clean poweroff.
        self.proxy.Kill("leader", signal.SIGRTMIN + 4)

    def addresses(self, wait: bool = True) -> list[str]:
        """Return the list of network addresses (ipv4 and ipv6) assigned to the
        container. When wait is True, the method waits until the list of IP addresses is
        not empty."""
        found_v4 = False
        found_v6 = False
        result = []
        # machine1 DBus interface returns a sequence of pairs: the 1st element is the
        # address type and the 2nd element is a tuple with address all bytes as separate
        # integers.
        while True:
            try:
                for address in self.proxy.GetAddresses():
                    if address[0] == int(socket.AF_INET):
                        found_v4 = True
                        # Join all bytes with . to build an IPv4 address
                        result.append(
                            ipaddress.IPv4Address(".".join(map(str, address[1])))
                        )
                    elif address[0] == int(socket.AF_INET6):
                        found_v6 = True
                        # Join with : all 2 bytes converted a string of hex values
                        result.append(
                            ipaddress.IPv6Address(
                                ":".join(
                                    [
                                        f"{a:x}{b:x}"
                                        for a, b in zip(*[iter(address[1])] * 2)
                                    ]
                                )
                            )
                        )
                    else:
                        logger.error(
                            "Unsupported socket type %d for address of container %s",
                            address[0],
                            self.name,
                        )
            except DBusError as err:
                raise FireHPCRuntimeError(
                    f"DBus error while getting IP addresses of {self.name}: {err}"
                ) from err
            if (found_v4 and found_v6) or not wait:
                break  # stop main while loop
            else:
                logger.debug(
                    "IP addresses of containers %s are not yet available, retrying…",
                    self.name,
                )
                time.sleep(1)
        return result

    @staticmethod
    def start(name, cluster, namespace) -> None:
        service = ContainerService(name, cluster, namespace)
        service.start()

    @classmethod
    def from_machine(cls, machine, cluster) -> Container:
        (name, cluster, namespace) = machine[0].split(".", 3)
        return cls(name, cluster, namespace, machine[3])

    @classmethod
    def from_machine_path(cls, path) -> Container:
        obj = DBus().proxy(cls.INTERFACE, path)
        (name, cluster, namespace) = obj.Name.split(".", 3)
        return cls(
            name,
            cluster,
            namespace,
            path,
        )


class ContainerImage(DBusObject):
    INTERFACE = "org.freedesktop.machine1"

    def __init__(
        self,
        name: str,
        cluster: str,
        namespace: str,
        creation: int,
        modification: int,
        volume: int,
        path: str,
    ):
        super().__init__(path)
        self.name = name
        self.cluster = cluster
        self.namespace = namespace
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

    def clone(self, node: str) -> None:
        target = f"{node}.{self.cluster}.{self.namespace}"
        self.proxy.Clone(target, False)

    @classmethod
    def from_machine_image(cls, image) -> ContainerImage:
        (name, cluster, namespace) = image[0].split(".", 3)
        return cls(
            name,
            cluster,
            namespace,
            image[3],
            image[4],
            image[5],
            image[6],
        )

    @classmethod
    def from_machine_image_path(cls, path: str) -> ContainerImage:
        obj = DBus().proxy(cls.INTERFACE, path)
        (name, cluster, namespace) = obj.Name.split(".", 3)
        return cls(
            name,
            cluster,
            namespace,
            obj.CreationTimestamp,
            obj.CreationTimestamp,
            obj.Usage,
            path,
        )


class ContainersManager(DBusObject):
    INTERFACE = "org.freedesktop.machine1"

    def __init__(self, cluster: str) -> ContainersManager:
        super().__init__("/org/freedesktop/machine1")
        self.cluster = cluster
        self.namespace = os.getlogin()

    def running(self) -> list:
        return [
            Container.from_machine(machine, self.cluster)
            for machine in self.proxy.ListMachines()
            if machine[0].endswith(f".{self.cluster}.{self.namespace}")
            and machine[1] == "container"
        ]

    def container(self, name) -> Container:
        return Container.from_machine_path(
            self.proxy.GetMachine(f"{name}.{self.cluster}.{self.namespace}")
        )

    def images(self) -> list:
        return [
            ContainerImage.from_machine_image(image)
            for image in self.proxy.ListImages()
            if image[0].endswith(f".{self.cluster}.{self.namespace}")
        ]

    def image(self, name) -> ContainerImage:
        return ContainerImage.from_machine_image_path(self.proxy.GetImage(name))

    def download(self, node: str, url: str) -> ContainerImage:
        name = f"{node}.{self.cluster}.{self.namespace}"
        ImageImporter(url, name).transfer()
        return ContainerImage.from_machine_image_path(self.proxy.GetImage(name))

    def storage(self) -> StorageService:
        return StorageService(self.cluster, self.namespace)

    def start(self, containers: list):
        ClusterStateModifier(self.cluster, self.namespace).start(containers)

    def stop(self):
        ClusterStateModifier(self.cluster, self.namespace).stop(self.running())
