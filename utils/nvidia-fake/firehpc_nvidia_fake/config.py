# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Load the description of the fake GPUs of the node.

The configuration file is JSON, for example:

    {
      "driver_version": "570.86.15",
      "cuda_version": "12.8",
      "flavor": "4.8.4",
      "gpus": [
        {
          "index": 0,
          "uuid": "GPU-8a1c6a52-2f05-5c3e-a4a4-0c0f1b3b7a10",
          "pci_bus_id": "00000000:10:00.0",
          "name": "NVIDIA H100 80GB HBM3",
          "architecture": "Hopper",
          "memory_mib": 81559,
          "power_idle_w": 70,
          "power_max_w": 700
        }
      ]
    }
"""

import json

DEFAULT_CONFIG_PATH = "/etc/firehpc/nvidia-fake.json"
DEFAULT_DRIVER_VERSION = "570.86.15"
DEFAULT_CUDA_VERSION = "12.8"

FLAVOR_LEGACY = "legacy"
FLAVOR_4_8_4 = "4.8.4"
FLAVOR_CURRENT = "current"
FLAVORS = (FLAVOR_LEGACY, FLAVOR_4_8_4, FLAVOR_CURRENT)
DEFAULT_FLAVOR = FLAVOR_4_8_4


class ConfigError(Exception):
    pass


class GPU:
    """Static description of one fake GPU."""

    def __init__(
        self,
        index,
        uuid,
        pci_bus_id,
        name,
        architecture,
        memory_mib,
        power_idle_w,
        power_max_w,
    ):
        self.index = index
        self.uuid = uuid
        self.pci_bus_id = pci_bus_id
        self.name = name
        self.architecture = architecture
        self.memory_mib = memory_mib
        self.power_idle_w = power_idle_w
        self.power_max_w = power_max_w

    @property
    def memory_bytes(self):
        return self.memory_mib * 2**20

    @property
    def device(self):
        return "nvidia{}".format(self.index)

    def __repr__(self):
        return "GPU({}, {}, {})".format(self.index, self.name, self.uuid)


class Config:
    def __init__(self, gpus, driver_version, cuda_version, flavor):
        self.gpus = gpus
        self.driver_version = driver_version
        self.cuda_version = cuda_version
        self.flavor = flavor


def _require(entry, key, kind, position):
    if key not in entry:
        raise ConfigError("GPU #{}: missing key {}".format(position, key))
    value = entry[key]
    # bool is a subclass of int, reject it explicitly.
    if isinstance(value, bool) or not isinstance(value, kind):
        raise ConfigError(
            "GPU #{}: invalid value for {}: {!r}".format(position, key, value)
        )
    return value


def _gpu_from_dict(entry, position):
    if not isinstance(entry, dict):
        raise ConfigError("GPU #{}: entry must be an object".format(position))
    gpu = GPU(
        index=_require(entry, "index", int, position),
        uuid=_require(entry, "uuid", str, position),
        pci_bus_id=_require(entry, "pci_bus_id", str, position),
        name=_require(entry, "name", str, position),
        architecture=_require(entry, "architecture", str, position),
        memory_mib=_require(entry, "memory_mib", int, position),
        power_idle_w=float(_require(entry, "power_idle_w", (int, float), position)),
        power_max_w=float(_require(entry, "power_max_w", (int, float), position)),
    )
    if gpu.memory_mib <= 0:
        raise ConfigError("GPU #{}: memory_mib must be positive".format(position))
    if not 0 <= gpu.power_idle_w < gpu.power_max_w:
        raise ConfigError(
            "GPU #{}: power_idle_w must be >= 0 and lower than power_max_w".format(
                position
            )
        )
    return gpu


def parse_config(data):
    """Build a Config from decoded JSON data."""
    if not isinstance(data, dict):
        raise ConfigError("configuration must be an object")
    flavor = data.get("flavor", DEFAULT_FLAVOR)
    if flavor not in FLAVORS:
        raise ConfigError(
            "unsupported flavor {!r}, expected one of {}".format(
                flavor, ", ".join(FLAVORS)
            )
        )
    entries = data.get("gpus", [])
    if not isinstance(entries, list):
        raise ConfigError("gpus must be a list")
    gpus = [_gpu_from_dict(entry, position) for position, entry in enumerate(entries)]
    # Indexes must be 0..N-1 in order: Slurm and CEEMS use the position of the
    # GPU as its index.
    for position, gpu in enumerate(gpus):
        if gpu.index != position:
            raise ConfigError(
                "GPU #{}: index {} does not match its position".format(
                    position, gpu.index
                )
            )
    uuids = [gpu.uuid for gpu in gpus]
    if len(set(uuids)) != len(uuids):
        raise ConfigError("GPU UUIDs must be unique")
    return Config(
        gpus=gpus,
        driver_version=str(data.get("driver_version", DEFAULT_DRIVER_VERSION)),
        cuda_version=str(data.get("cuda_version", DEFAULT_CUDA_VERSION)),
        flavor=flavor,
    )


def load_config(path=DEFAULT_CONFIG_PATH):
    try:
        with open(path) as fh:
            data = json.load(fh)
    except OSError as err:
        raise ConfigError("unable to read {}: {}".format(path, err))
    except ValueError as err:
        raise ConfigError("invalid JSON in {}: {}".format(path, err))
    return parse_config(data)
