# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import io
import xml.etree.ElementTree as ET

import pytest

from firehpc_nvidia_fake.smi import list_gpus, query_xml, run


def _parse(text):
    # Drop the DOCTYPE line, ElementTree does not need the DTD.
    return ET.fromstring("\n".join(text.splitlines()[2:]))


def test_query_xml_ceems_fields(config):
    root = _parse(query_xml(config))
    assert root.tag == "nvidia_smi_log"
    assert root.findtext("driver_version") == "570.86.15"
    assert root.findtext("attached_gpus") == "3"
    gpus = root.findall("gpu")
    assert len(gpus) == 3
    # CEEMS uses the position in the XML as GPU index.
    for position, (element, gpu) in enumerate(zip(gpus, config.gpus)):
        assert element.get("id") == gpu.pci_bus_id
        assert element.findtext("product_name") == gpu.name
        assert element.findtext("product_brand") == "NVIDIA"
        assert element.findtext("product_architecture") == "Hopper"
        assert element.findtext("mig_mode/current_mig") == "Disabled"
        assert element.findtext("gpu_virtualization_mode/virtualization_mode") == "None"
        assert element.findtext("gpu_virtualization_mode/host_vgpu_mode") == "N/A"
        assert element.findtext("uuid") == gpu.uuid
        assert element.findtext("minor_number") == str(position)
        assert element.findtext("fb_memory_usage/total") == "81559 MiB"


def test_query_xml_header(config):
    lines = query_xml(config).splitlines()
    assert lines[0] == '<?xml version="1.0" ?>'
    assert lines[1].startswith("<!DOCTYPE nvidia_smi_log")


def test_list_gpus(config):
    lines = list_gpus(config).splitlines()
    assert lines == [
        "GPU {}: {} (UUID: {})".format(gpu.index, gpu.name, gpu.uuid)
        for gpu in config.gpus
    ]


@pytest.mark.parametrize(
    "argv",
    [["--query", "--xml-format"], ["-q", "-x"], ["-qx"]],
)
def test_run_query(config_file, argv):
    out = io.StringIO()
    assert run(["--config", str(config_file)] + argv, out) == 0
    assert len(_parse(out.getvalue()).findall("gpu")) == 3


@pytest.mark.parametrize("argv", [["-L"], ["--list-gpus"]])
def test_run_list(config_file, argv):
    out = io.StringIO()
    assert run(["--config", str(config_file)] + argv, out) == 0
    assert out.getvalue().startswith("GPU 0: NVIDIA H100 80GB HBM3 (UUID: GPU-")


def test_run_summary(config_file):
    out = io.StringIO()
    assert run(["--config", str(config_file)], out) == 0
    assert "Driver Version: 570.86.15" in out.getvalue()
    assert "00000000:12:00.0" in out.getvalue()


def test_run_query_without_xml(config_file):
    assert run(["--config", str(config_file), "-q"], io.StringIO()) == 2


def test_run_unknown_option(config_file):
    with pytest.raises(SystemExit) as exc:
        run(["--config", str(config_file), "--query-gpu=name"], io.StringIO())
    assert exc.value.code != 0


def test_run_missing_config(tmp_path):
    assert run(["--config", str(tmp_path / "missing"), "-L"], io.StringIO()) == 9
