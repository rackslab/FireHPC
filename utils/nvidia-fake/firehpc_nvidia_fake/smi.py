# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""firehpc-nvidia-smi: the subset of nvidia-smi used by GPU monitoring tools.

Supported commands:

- ``-q -x`` / ``--query --xml-format``: XML report, as parsed by the CEEMS
  exporter for GPU discovery (product name, brand, architecture, MIG and
  virtualization modes, UUID, minor number, PCI bus id in the gpu id
  attribute).
- ``-L`` / ``--list-gpus``: one line per GPU.
- no argument: a short summary table.
"""

import argparse
import sys
import time
import xml.etree.ElementTree as ET

from .config import DEFAULT_CONFIG_PATH, ConfigError, load_config

XML_HEADER = (
    '<?xml version="1.0" ?>\n<!DOCTYPE nvidia_smi_log SYSTEM "nvsmi_device_v12.dtd">\n'
)


def _sub(parent, tag, text=None):
    element = ET.SubElement(parent, tag)
    if text is not None:
        element.text = str(text)
    return element


def _indent(element, level=0):
    # ElementTree.indent() is only available with Python >= 3.9.
    pad = "\n" + "\t" * level
    if len(element):
        if not element.text or not element.text.strip():
            element.text = pad + "\t"
        for child in element:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = pad
    if level and (not element.tail or not element.tail.strip()):
        element.tail = pad


def _gpu_element(root, gpu):
    element = _sub(root, "gpu")
    element.set("id", gpu.pci_bus_id)
    _sub(element, "product_name", gpu.name)
    _sub(element, "product_brand", "NVIDIA")
    _sub(element, "product_architecture", gpu.architecture)
    _sub(element, "display_mode", "Disabled")
    _sub(element, "persistence_mode", "Enabled")
    mig = _sub(element, "mig_mode")
    _sub(mig, "current_mig", "Disabled")
    _sub(mig, "pending_mig", "Disabled")
    _sub(element, "mig_devices", "None")
    _sub(element, "serial", "{:013d}".format(1650000000000 + gpu.index))
    _sub(element, "uuid", gpu.uuid)
    _sub(element, "minor_number", gpu.index)
    virt = _sub(element, "gpu_virtualization_mode")
    _sub(virt, "virtualization_mode", "None")
    _sub(virt, "host_vgpu_mode", "N/A")
    pci = _sub(element, "pci")
    bus_id = gpu.pci_bus_id.split(":")
    _sub(pci, "pci_bus", bus_id[1] if len(bus_id) > 1 else "00")
    _sub(pci, "pci_device", "00")
    _sub(pci, "pci_domain", "0000")
    _sub(pci, "pci_bus_id", gpu.pci_bus_id)
    fb = _sub(element, "fb_memory_usage")
    _sub(fb, "total", "{} MiB".format(gpu.memory_mib))
    _sub(fb, "reserved", "0 MiB")
    _sub(fb, "used", "0 MiB")
    _sub(fb, "free", "{} MiB".format(gpu.memory_mib))
    power = _sub(element, "gpu_power_readings")
    _sub(power, "current_power_limit", "{:.2f} W".format(gpu.power_max_w))
    _sub(power, "max_power_limit", "{:.2f} W".format(gpu.power_max_w))
    _sub(element, "processes")


def query_xml(config, now=None):
    """Return the nvidia-smi -q -x report."""
    root = ET.Element("nvidia_smi_log")
    _sub(root, "timestamp", time.strftime("%a %b %d %H:%M:%S %Y", time.localtime(now)))
    _sub(root, "driver_version", config.driver_version)
    _sub(root, "cuda_version", config.cuda_version)
    _sub(root, "attached_gpus", len(config.gpus))
    for gpu in config.gpus:
        _gpu_element(root, gpu)
    _indent(root)
    return XML_HEADER + ET.tostring(root, encoding="unicode") + "\n"


def list_gpus(config):
    """Return the nvidia-smi -L output."""
    return "".join(
        "GPU {}: {} (UUID: {})\n".format(gpu.index, gpu.name, gpu.uuid)
        for gpu in config.gpus
    )


def summary(config):
    """Return a short summary table, close to plain nvidia-smi output."""
    lines = [
        "FireHPC fake nvidia-smi    Driver Version: {}    CUDA Version: {}".format(
            config.driver_version, config.cuda_version
        ),
        "{:<4} {:<28} {:<17} {:>12} {:>10}".format(
            "GPU", "Name", "Bus-Id", "Memory", "Power Cap"
        ),
    ]
    for gpu in config.gpus:
        lines.append(
            "{:<4} {:<28} {:<17} {:>8} MiB {:>8.0f} W".format(
                gpu.index,
                gpu.name[:28],
                gpu.pci_bus_id,
                gpu.memory_mib,
                gpu.power_max_w,
            )
        )
    if not config.gpus:
        lines.append("No devices were found")
    return "\n".join(lines) + "\n"


def parser():
    result = argparse.ArgumentParser(
        prog="firehpc-nvidia-smi",
        description="Fake nvidia-smi for FireHPC emulated GPU nodes",
    )
    result.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Path to fake GPUs configuration file (default: %(default)s)",
    )
    result.add_argument(
        "-q", "--query", action="store_true", help="Display GPU information"
    )
    result.add_argument(
        "-x", "--xml-format", action="store_true", help="Produce XML output"
    )
    result.add_argument(
        "-L", "--list-gpus", action="store_true", help="Display a list of GPUs"
    )
    return result


def run(argv, out):
    """Run the command with argv and write to out. Returns the exit code."""
    args = parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as err:
        sys.stderr.write("firehpc-nvidia-smi: {}\n".format(err))
        return 9  # nvidia-smi exit code for driver errors
    if args.list_gpus:
        out.write(list_gpus(config))
    elif args.query:
        if not args.xml_format:
            sys.stderr.write("firehpc-nvidia-smi: only XML query output is supported\n")
            return 2
        out.write(query_xml(config))
    elif args.xml_format:
        sys.stderr.write("firehpc-nvidia-smi: -x requires -q\n")
        return 2
    else:
        out.write(summary(config))
    return 0


def main():
    sys.exit(run(sys.argv[1:], sys.stdout))
