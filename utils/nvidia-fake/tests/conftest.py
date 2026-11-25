# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json

import pytest

from firehpc_nvidia_fake.config import parse_config


def gpu_dict(index, name="NVIDIA H100 80GB HBM3", memory_mib=81559):
    return {
        "index": index,
        "uuid": "GPU-00000000-0000-0000-0000-00000000000{}".format(index),
        "pci_bus_id": "00000000:{:02X}:00.0".format(0x10 + index),
        "name": name,
        "architecture": "Hopper",
        "memory_mib": memory_mib,
        "power_idle_w": 70,
        "power_max_w": 700,
    }


@pytest.fixture
def config_data():
    return {
        "driver_version": "570.86.15",
        "cuda_version": "12.8",
        "flavor": "4.8.4",
        "gpus": [gpu_dict(0), gpu_dict(1), gpu_dict(2, name="NVIDIA H200")],
    }


@pytest.fixture
def config(config_data):
    return parse_config(config_data)


@pytest.fixture
def config_file(tmp_path, config_data):
    path = tmp_path / "nvidia-fake.json"
    path.write_text(json.dumps(config_data))
    return path


def write_environ(proc_root, pid, environ):
    directory = proc_root / str(pid)
    directory.mkdir(parents=True)
    data = b"".join(
        "{}={}".format(key, value).encode() + b"\0" for key, value in environ.items()
    )
    (directory / "environ").write_bytes(data)
    return directory
