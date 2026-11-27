# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import random
import re
import threading
import urllib.error
import urllib.request

import pytest
from prometheus_client.parser import text_string_to_metric_families

from firehpc_nvidia_fake import catalog
from firehpc_nvidia_fake.dcgm import (
    Exporter,
    escape_label,
    format_value,
    make_server,
    parse_listen,
)

from conftest import write_environ

# DCGM metrics read by CEEMS recording rules (nvidia-dcgm-gpu.rules), with
# their equivalent in current flavor.
CEEMS_LEGACY = [
    "DCGM_FI_DEV_GPU_UTIL",
    "DCGM_FI_DEV_POWER_USAGE_INSTANT",
    "DCGM_FI_DEV_FB_USED",
    "DCGM_FI_DEV_FB_FREE",
    "DCGM_FI_PROF_GR_ENGINE_ACTIVE",
    "DCGM_FI_PROF_SM_ACTIVE",
    "DCGM_FI_PROF_SM_OCCUPANCY",
    "DCGM_FI_PROF_PIPE_TENSOR_ACTIVE",
    "DCGM_FI_PROF_PIPE_FP64_ACTIVE",
    "DCGM_FI_PROF_PIPE_FP32_ACTIVE",
    "DCGM_FI_PROF_PIPE_FP16_ACTIVE",
    "DCGM_FI_PROF_DRAM_ACTIVE",
    "DCGM_FI_PROF_PCIE_TX_BYTES",
    "DCGM_FI_PROF_PCIE_RX_BYTES",
    "DCGM_FI_PROF_NVLINK_TX_BYTES",
    "DCGM_FI_PROF_NVLINK_RX_BYTES",
]
CEEMS_CURRENT = [
    "DCGM_FI_DEV_GPU_UTIL_RATIO",
    "DCGM_FI_DEV_BOARD_POWER_RAW_WATTS",
    "DCGM_FI_DEV_FB_USED_BYTES",
    "DCGM_FI_DEV_FB_FREE_BYTES",
    "DCGM_FI_PROF_GR_ENGINE_UTIL_RATIO",
    "DCGM_FI_PROF_SM_UTIL_RATIO",
    "DCGM_FI_PROF_SM_OCCUPANCY_RATIO",
    "DCGM_FI_PROF_TENSOR_UTIL_RATIO",
    "DCGM_FI_PROF_FP64_UTIL_RATIO",
    "DCGM_FI_PROF_FP32_UTIL_RATIO",
    "DCGM_FI_PROF_FP16_UTIL_RATIO",
    "DCGM_FI_PROF_DRAM_UTIL_RATIO",
    "DCGM_FI_PROF_PCIE_TX_BYTES",
    "DCGM_FI_PROF_PCIE_RX_BYTES",
    "DCGM_FI_PROF_NVLINK_TX_BYTES",
    "DCGM_FI_PROF_NVLINK_RX_BYTES",
]

EXPECTED = {
    "legacy": (CEEMS_LEGACY, "Hostname", "DCGM_FI_DRIVER_VERSION"),
    "4.8.4": (CEEMS_LEGACY, "hostname", "DCGM_FI_DRIVER_VERSION"),
    "current": (CEEMS_CURRENT, "hostname", "DCGM_FI_SYSTEM_DRIVER_VERSION"),
}


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def _exporter(config, tmp_path, flavor, jobs=None):
    for pid, (job_id, gpus) in enumerate((jobs or {}).items(), start=100):
        write_environ(tmp_path, pid, {"SLURM_JOB_ID": job_id, "SLURM_JOB_GPUS": gpus})
    clock = Clock()
    exporter = Exporter(
        config,
        flavor=flavor,
        hostname="cn01",
        proc_root=str(tmp_path),
        clock=clock,
        rng=random.Random(1),
    )
    return exporter, clock


def _samples(text):
    """Return {(metric, gpu): (value, labels)} and the families types."""
    samples = {}
    types = {}
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            name = sample.name
            # The parser appends _total to counter samples, the emitted names
            # never end with lowercase _total.
            if family.type == "counter" and name.endswith("_total"):
                name = name[: -len("_total")]
            types[name] = family.type
            samples[(name, sample.labels["gpu"])] = (
                sample.value,
                sample.labels,
            )
    return samples, types


@pytest.mark.parametrize("flavor", list(EXPECTED))
def test_flavor_names_and_labels(config, tmp_path, flavor):
    expected, host_label, driver_label = EXPECTED[flavor]
    exporter, _ = _exporter(config, tmp_path, flavor)
    samples, _ = _samples(exporter.render())
    names = {name for name, _ in samples}
    for name in expected:
        assert name in names, name
    other = CEEMS_CURRENT if flavor != "current" else CEEMS_LEGACY
    for name in set(other) - set(expected):
        assert name not in names, name
    _, labels = samples[("DCGM_FI_PROF_PCIE_TX_BYTES", "1")]
    assert labels == {
        "gpu": "1",
        "UUID": config.gpus[1].uuid,
        "pci_bus_id": "00000000:11:00.0",
        "device": "nvidia1",
        "modelName": "NVIDIA H100 80GB HBM3",
        host_label: "cn01",
        driver_label: "570.86.15",
    }


def test_flavor_from_config(config, tmp_path):
    config.flavor = "current"
    exporter = Exporter(config, hostname="cn01", proc_root=str(tmp_path))
    assert "DCGM_FI_DEV_GPU_UTIL_RATIO{" in exporter.render()


def test_counter_names_without_total_suffix(config, tmp_path):
    exporter, _ = _exporter(config, tmp_path, "4.8.4")
    text = exporter.render()
    assert "# TYPE DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION counter" in text
    assert "DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION_total" not in text


def test_exposition_format(config, tmp_path):
    exporter, _ = _exporter(config, tmp_path, "4.8.4")
    line_re = re.compile(
        r"^(# (HELP|TYPE) [A-Z0-9_]+ .+"
        r'|[A-Z0-9_]+\{([A-Za-z_]+="[^"]*",?)+\} [-0-9.e+]+)$'
    )
    for line in exporter.render().splitlines():
        assert line_re.match(line), line


def test_busy_gpus_follow_jobs(config, tmp_path):
    exporter, clock = _exporter(config, tmp_path, "4.8.4", jobs={"42": "0,2"})
    for _ in range(60):
        exporter.render()
        clock.now += 1.0
    samples, _ = _samples(exporter.render())
    util = {gpu: samples[("DCGM_FI_DEV_GPU_UTIL", gpu)][0] for gpu in "012"}
    assert util["0"] >= 39
    assert util["2"] >= 39
    assert util["1"] == 0
    power = {gpu: samples[("DCGM_FI_DEV_POWER_USAGE", gpu)][0] for gpu in "012"}
    assert power["1"] == 70
    assert power["0"] > 200


def test_unit_conversions(config, tmp_path):
    legacy, legacy_clock = _exporter(config, tmp_path / "a", "4.8.4", {"42": "0"})
    current, current_clock = _exporter(config, tmp_path / "b", "current", {"42": "0"})
    for _ in range(30):
        legacy_text = legacy.render()
        current_text = current.render()
        legacy_clock.now += 1.0
        current_clock.now += 1.0
    # Same seeds and same steps, both simulations are identical.
    old, _ = _samples(legacy_text)
    new, _ = _samples(current_text)

    def pair(old_name, new_name):
        return old[(old_name, "0")][0], new[(new_name, "0")][0]

    a, b = pair("DCGM_FI_DEV_GPU_UTIL", "DCGM_FI_DEV_GPU_UTIL_RATIO")
    # Legacy integer fields are rounded.
    assert a == pytest.approx(b * 100, abs=0.5)
    a, b = pair("DCGM_FI_DEV_FB_USED", "DCGM_FI_DEV_FB_USED_BYTES")
    assert a * 2**20 == pytest.approx(b)
    a, b = pair(
        "DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION", "DCGM_FI_DEV_GPU_ENERGY_JOULES_TOTAL"
    )
    assert b > 0
    assert a == pytest.approx(b * 1000, abs=0.5)
    a, b = pair("DCGM_FI_DEV_SM_CLOCK", "DCGM_FI_DEV_SM_CLOCK_HERTZ")
    assert a == pytest.approx(b / 1e6, abs=0.5)
    a, b = pair(
        "DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL",
        "DCGM_FI_DEV_NVLINK_THROUGHPUT_BYTES_PER_SECOND",
    )
    assert a == pytest.approx(b / 1e6, abs=0.5)


def test_integer_fields(config, tmp_path):
    exporter, clock = _exporter(config, tmp_path, "4.8.4", jobs={"42": "0"})
    for _ in range(20):
        exporter.render()
        clock.now += 1.0
    samples, _ = _samples(exporter.render())
    for (name, _), (value, _) in samples.items():
        if name in catalog.INTEGER_NAMES:
            assert value == int(value), name
    assert samples[("DCGM_FI_DEV_FB_USED", "0")][0] > 0
    assert samples[("DCGM_FI_DEV_POWER_USAGE", "0")][0] != int(
        samples[("DCGM_FI_DEV_POWER_USAGE", "0")][0]
    )


def test_catalog_integer_names_known():
    names = set()
    for flavor in EXPECTED:
        names.update(name for name, _, _, _ in catalog.metrics(flavor))
    assert catalog.INTEGER_NAMES <= names


def test_catalog_names_unique():
    for flavor in EXPECTED:
        names = [name for name, _, _, _ in catalog.metrics(flavor)]
        assert len(names) == len(set(names)), flavor


def test_escape_label():
    assert escape_label('a"b\\c\nd') == 'a\\"b\\\\c\\nd'


def test_format_value():
    assert format_value(1980000000.0) == "1980000000"
    assert format_value(0.5) == "0.5"
    assert format_value(0) == "0"


def test_parse_listen():
    assert parse_listen(":9400") == ("", 9400)
    assert parse_listen("127.0.0.1:9401") == ("127.0.0.1", 9401)
    assert parse_listen("[::1]:9400") == ("::1", 9400)
    with pytest.raises(Exception):
        parse_listen("9400x")


def test_http(config, tmp_path):
    exporter, _ = _exporter(config, tmp_path, "4.8.4")
    server = make_server(exporter, ("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = "http://127.0.0.1:{}".format(server.server_address[1])
        with urllib.request.urlopen(url + "/metrics") as response:
            assert response.status == 200
            assert response.headers["Content-Type"].startswith("text/plain")
            assert b"DCGM_FI_DEV_GPU_UTIL{" in response.read()
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(url + "/other")
        assert exc.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
