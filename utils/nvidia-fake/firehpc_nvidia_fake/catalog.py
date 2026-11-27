# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Metrics emitted by the fake DCGM exporter, for each flavor.

DCGM 4.6 and 4.7 renamed most fields and changed some units (MHz to Hz, MiB
to bytes, percent to ratio, mJ to J). The default counters of dcgm-exporter
4.8.4 still use the legacy names, while those of 4.9.0 and later use the new
names. DCGM still resolves the deprecated names, which the exporter emits as
listed in its counters CSV, so 4.9.0 with a CSV of legacy names (like the one
recommended by CEEMS) matches the 4.8.4 flavor. Exporters from 4.8.3 on also
renamed the Hostname label to hostname.

Names and types come from:

- https://github.com/NVIDIA/dcgm-exporter/blob/4.8.4/etc/default-counters.csv
- https://github.com/NVIDIA/dcgm-exporter/blob/4.9.0/etc/default-counters.csv
- https://github.com/NVIDIA/dcgm-exporter/blob/4.9.0/internal/pkg/counters/default_counter_sources_test.go
- https://github.com/NVIDIA/go-dcgm/blob/v1.4712.2/pkg/dcgm/const_fields.go
- https://github.com/NVIDIA/DCGM/blob/master/dcgmlib/dcgm_fields.h
- https://docs.nvidia.com/datacenter/dcgm/latest/release-notes/changelog.html

The set covers the exporter default counters plus the profiling counters that
the CEEMS recording rules read (SM_ACTIVE, SM_OCCUPANCY, PIPE_FP*_ACTIVE,
NVLINK_*_BYTES, POWER_USAGE_INSTANT), as when the exporter runs with all
profiling counters enabled as CEEMS recommends.

The deprecated DCGM_FI_DEV_PCIE_TX/RX_THROUGHPUT fields are not emitted,
dcgm-exporter 4.8.4 dropped them from its default configuration.
"""

from .config import FLAVOR_4_8_4, FLAVOR_CURRENT, FLAVOR_LEGACY

GAUGE = "gauge"
COUNTER = "counter"

PERCENT = 100.0
MHZ = 1e-6
MIB = 1.0 / 2**20
MB = 1e-6
MILLI = 1000.0


class MetricDef:
    """One emitted metric.

    quantity is the key in GPUModel.values(). legacy and current are
    (name, scale) or (name, scale, help) tuples, or None when the flavor does
    not emit the metric. The emitted value is the quantity multiplied by the
    scale. Help defaults to the help of the metric.
    """

    def __init__(self, quantity, kind, help, legacy, current):
        self.quantity = quantity
        self.kind = kind
        self.help = help
        self.legacy = legacy
        self.current = current

    def naming(self, flavor):
        """Return (name, scale, help) for flavor, or None."""
        naming = self.current if flavor == FLAVOR_CURRENT else self.legacy
        if naming is None:
            return None
        if len(naming) == 2:
            return naming + (self.help,)
        return naming


CATALOG = [
    MetricDef(
        "sm_clock",
        GAUGE,
        "SM clock frequency",
        ("DCGM_FI_DEV_SM_CLOCK", MHZ, "SM clock frequency (in MHz)."),
        ("DCGM_FI_DEV_SM_CLOCK_HERTZ", 1.0, "SM clock frequency in hertz."),
    ),
    MetricDef(
        "memory_clock",
        GAUGE,
        "Memory clock frequency",
        ("DCGM_FI_DEV_MEM_CLOCK", MHZ, "Memory clock frequency (in MHz)."),
        ("DCGM_FI_DEV_MEMORY_CLOCK_HERTZ", 1.0, "Memory clock frequency in hertz."),
    ),
    MetricDef(
        "memory_temp",
        GAUGE,
        "Memory temperature (in C).",
        ("DCGM_FI_DEV_MEMORY_TEMP", 1.0),
        ("DCGM_FI_DEV_MEMORY_TEMP_CELSIUS", 1.0),
    ),
    MetricDef(
        "gpu_temp",
        GAUGE,
        "GPU temperature (in C).",
        ("DCGM_FI_DEV_GPU_TEMP", 1.0),
        ("DCGM_FI_DEV_GPU_TEMP_CELSIUS", 1.0),
    ),
    MetricDef(
        "power",
        GAUGE,
        "Power draw (in W).",
        ("DCGM_FI_DEV_POWER_USAGE", 1.0),
        ("DCGM_FI_DEV_BOARD_POWER_WATTS", 1.0),
    ),
    # Not in exporter default counters, read by CEEMS power rules. DCGM 4.6
    # deprecated POWER_USAGE_INSTANT for BOARD_POWER_RAW_WATTS (field 157).
    MetricDef(
        "power_instant",
        GAUGE,
        "Current instantaneous power usage (in W).",
        ("DCGM_FI_DEV_POWER_USAGE_INSTANT", 1.0),
        ("DCGM_FI_DEV_BOARD_POWER_RAW_WATTS", 1.0),
    ),
    MetricDef(
        "energy",
        COUNTER,
        "Total energy consumption since boot",
        (
            "DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION",
            MILLI,
            "Total energy consumption since boot (in mJ).",
        ),
        (
            "DCGM_FI_DEV_GPU_ENERGY_JOULES_TOTAL",
            1.0,
            "GPU energy consumed since driver reload (in J).",
        ),
    ),
    MetricDef(
        "zero",
        COUNTER,
        "Total number of PCIe retries.",
        ("DCGM_FI_DEV_PCIE_REPLAY_COUNTER", 1.0),
        ("DCGM_FI_DEV_PCIE_REPLAY_TOTAL", 1.0),
    ),
    MetricDef(
        "util",
        GAUGE,
        "GPU utilization",
        ("DCGM_FI_DEV_GPU_UTIL", PERCENT, "GPU utilization (in %)."),
        ("DCGM_FI_DEV_GPU_UTIL_RATIO", 1.0, "GPU utilization as a ratio."),
    ),
    MetricDef(
        "memory_util",
        GAUGE,
        "Memory utilization",
        ("DCGM_FI_DEV_MEM_COPY_UTIL", PERCENT, "Memory utilization (in %)."),
        ("DCGM_FI_DEV_MEMORY_UTIL_RATIO", 1.0, "Memory utilization as a ratio."),
    ),
    MetricDef(
        "enc_util",
        GAUGE,
        "Encoder utilization",
        ("DCGM_FI_DEV_ENC_UTIL", PERCENT, "Encoder utilization (in %)."),
        ("DCGM_FI_DEV_ENC_UTIL_RATIO", 1.0, "Encoder utilization as a ratio."),
    ),
    MetricDef(
        "dec_util",
        GAUGE,
        "Decoder utilization",
        ("DCGM_FI_DEV_DEC_UTIL", PERCENT, "Decoder utilization (in %)."),
        ("DCGM_FI_DEV_DEC_UTIL_RATIO", 1.0, "Decoder utilization as a ratio."),
    ),
    MetricDef(
        "zero",
        GAUGE,
        "Value of the last XID error encountered.",
        ("DCGM_FI_DEV_XID_ERRORS", 1.0),
        ("DCGM_FI_DEV_XID_ERROR", 1.0),
    ),
    MetricDef(
        "fb_total",
        GAUGE,
        "Total framebuffer capacity in bytes.",
        None,
        ("DCGM_FI_DEV_FB_CAPACITY_BYTES", 1.0),
    ),
    MetricDef(
        "fb_free",
        GAUGE,
        "Framebuffer memory free",
        ("DCGM_FI_DEV_FB_FREE", MIB, "Framebuffer memory free (in MiB)."),
        ("DCGM_FI_DEV_FB_FREE_BYTES", 1.0, "Free framebuffer memory in bytes."),
    ),
    MetricDef(
        "fb_used",
        GAUGE,
        "Framebuffer memory used",
        ("DCGM_FI_DEV_FB_USED", MIB, "Framebuffer memory used (in MiB)."),
        ("DCGM_FI_DEV_FB_USED_BYTES", 1.0, "Used framebuffer memory in bytes."),
    ),
    MetricDef(
        "fb_reserved",
        GAUGE,
        "Framebuffer memory reserved",
        ("DCGM_FI_DEV_FB_RESERVED", MIB, "Framebuffer memory reserved (in MiB)."),
        (
            "DCGM_FI_DEV_FB_RESERVED_BYTES",
            1.0,
            "Reserved framebuffer memory in bytes.",
        ),
    ),
    MetricDef(
        "nvlink_total",
        GAUGE,
        "Aggregate NVLink throughput across all lanes",
        (
            "DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL",
            MB,
            "Aggregate NVLink throughput across all lanes (in MB/s).",
        ),
        (
            "DCGM_FI_DEV_NVLINK_THROUGHPUT_BYTES_PER_SECOND",
            1.0,
            "Total NVLink throughput across all lanes in bytes per second.",
        ),
    ),
    MetricDef(
        "zero",
        COUNTER,
        "Number of remapped rows for uncorrectable errors",
        ("DCGM_FI_DEV_UNCORRECTABLE_REMAPPED_ROWS", 1.0),
        ("DCGM_FI_DEV_ROW_REMAP_UNCORRECTABLE_TOTAL", 1.0),
    ),
    MetricDef(
        "zero",
        COUNTER,
        "Number of remapped rows for correctable errors",
        ("DCGM_FI_DEV_CORRECTABLE_REMAPPED_ROWS", 1.0),
        ("DCGM_FI_DEV_ROW_REMAP_CORRECTABLE_TOTAL", 1.0),
    ),
    MetricDef(
        "zero",
        GAUGE,
        "Whether remapping of rows has failed",
        ("DCGM_FI_DEV_ROW_REMAP_FAILURE", 1.0),
        ("DCGM_FI_DEV_ROW_REMAP_FAILED", 1.0),
    ),
    MetricDef(
        "gr_engine_active",
        GAUGE,
        "Ratio of time the graphics engine is active.",
        ("DCGM_FI_PROF_GR_ENGINE_ACTIVE", 1.0),
        ("DCGM_FI_PROF_GR_ENGINE_UTIL_RATIO", 1.0),
    ),
    MetricDef(
        "sm_active",
        GAUGE,
        "The ratio of cycles an SM has at least 1 warp assigned.",
        ("DCGM_FI_PROF_SM_ACTIVE", 1.0),
        ("DCGM_FI_PROF_SM_UTIL_RATIO", 1.0),
    ),
    MetricDef(
        "sm_occupancy",
        GAUGE,
        "The ratio of number of warps resident on an SM.",
        ("DCGM_FI_PROF_SM_OCCUPANCY", 1.0),
        ("DCGM_FI_PROF_SM_OCCUPANCY_RATIO", 1.0),
    ),
    MetricDef(
        "tensor_active",
        GAUGE,
        "Ratio of cycles the tensor (HMMA) pipe is active.",
        ("DCGM_FI_PROF_PIPE_TENSOR_ACTIVE", 1.0),
        ("DCGM_FI_PROF_TENSOR_UTIL_RATIO", 1.0),
    ),
    MetricDef(
        "fp64_active",
        GAUGE,
        "Ratio of cycles the fp64 pipes are active.",
        ("DCGM_FI_PROF_PIPE_FP64_ACTIVE", 1.0),
        ("DCGM_FI_PROF_FP64_UTIL_RATIO", 1.0),
    ),
    MetricDef(
        "fp32_active",
        GAUGE,
        "Ratio of cycles the fp32 pipes are active.",
        ("DCGM_FI_PROF_PIPE_FP32_ACTIVE", 1.0),
        ("DCGM_FI_PROF_FP32_UTIL_RATIO", 1.0),
    ),
    MetricDef(
        "fp16_active",
        GAUGE,
        "Ratio of cycles the fp16 pipes are active.",
        ("DCGM_FI_PROF_PIPE_FP16_ACTIVE", 1.0),
        ("DCGM_FI_PROF_FP16_UTIL_RATIO", 1.0),
    ),
    MetricDef(
        "dram_active",
        GAUGE,
        "Ratio of cycles the device memory interface is active sending or "
        "receiving data.",
        ("DCGM_FI_PROF_DRAM_ACTIVE", 1.0),
        ("DCGM_FI_PROF_DRAM_UTIL_RATIO", 1.0),
    ),
    MetricDef(
        "pcie_tx",
        GAUGE,
        "The rate of data transmitted over the PCIe bus - including both "
        "protocol headers and data payloads - in bytes per second.",
        ("DCGM_FI_PROF_PCIE_TX_BYTES", 1.0),
        ("DCGM_FI_PROF_PCIE_TX_BYTES", 1.0),
    ),
    MetricDef(
        "pcie_rx",
        GAUGE,
        "The rate of data received over the PCIe bus - including both "
        "protocol headers and data payloads - in bytes per second.",
        ("DCGM_FI_PROF_PCIE_RX_BYTES", 1.0),
        ("DCGM_FI_PROF_PCIE_RX_BYTES", 1.0),
    ),
    MetricDef(
        "nvlink_tx",
        GAUGE,
        "The rate of data transmitted over NVLink, not including protocol "
        "headers, in bytes per second.",
        ("DCGM_FI_PROF_NVLINK_TX_BYTES", 1.0),
        ("DCGM_FI_PROF_NVLINK_TX_BYTES", 1.0),
    ),
    MetricDef(
        "nvlink_rx",
        GAUGE,
        "The rate of data received over NVLink, not including protocol "
        "headers, in bytes per second.",
        ("DCGM_FI_PROF_NVLINK_RX_BYTES", 1.0),
        ("DCGM_FI_PROF_NVLINK_RX_BYTES", 1.0),
    ),
]

# DCGM int64 fields, emitted as integers by the real exporter. The other
# fields (ratios, watts) are doubles.
INTEGER_NAMES = frozenset(
    [
        "DCGM_FI_DEV_SM_CLOCK",
        "DCGM_FI_DEV_SM_CLOCK_HERTZ",
        "DCGM_FI_DEV_MEM_CLOCK",
        "DCGM_FI_DEV_MEMORY_CLOCK_HERTZ",
        "DCGM_FI_DEV_MEMORY_TEMP",
        "DCGM_FI_DEV_MEMORY_TEMP_CELSIUS",
        "DCGM_FI_DEV_GPU_TEMP",
        "DCGM_FI_DEV_GPU_TEMP_CELSIUS",
        "DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION",
        "DCGM_FI_DEV_PCIE_REPLAY_COUNTER",
        "DCGM_FI_DEV_PCIE_REPLAY_TOTAL",
        "DCGM_FI_DEV_GPU_UTIL",
        "DCGM_FI_DEV_MEM_COPY_UTIL",
        "DCGM_FI_DEV_ENC_UTIL",
        "DCGM_FI_DEV_DEC_UTIL",
        "DCGM_FI_DEV_XID_ERRORS",
        "DCGM_FI_DEV_XID_ERROR",
        "DCGM_FI_DEV_FB_CAPACITY_BYTES",
        "DCGM_FI_DEV_FB_FREE",
        "DCGM_FI_DEV_FB_FREE_BYTES",
        "DCGM_FI_DEV_FB_USED",
        "DCGM_FI_DEV_FB_USED_BYTES",
        "DCGM_FI_DEV_FB_RESERVED",
        "DCGM_FI_DEV_FB_RESERVED_BYTES",
        "DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL",
        "DCGM_FI_DEV_NVLINK_THROUGHPUT_BYTES_PER_SECOND",
        "DCGM_FI_DEV_UNCORRECTABLE_REMAPPED_ROWS",
        "DCGM_FI_DEV_ROW_REMAP_UNCORRECTABLE_TOTAL",
        "DCGM_FI_DEV_CORRECTABLE_REMAPPED_ROWS",
        "DCGM_FI_DEV_ROW_REMAP_CORRECTABLE_TOTAL",
        "DCGM_FI_DEV_ROW_REMAP_FAILURE",
        "DCGM_FI_DEV_ROW_REMAP_FAILED",
        "DCGM_FI_PROF_PCIE_TX_BYTES",
        "DCGM_FI_PROF_PCIE_RX_BYTES",
        "DCGM_FI_PROF_NVLINK_TX_BYTES",
        "DCGM_FI_PROF_NVLINK_RX_BYTES",
    ]
)

HOST_LABELS = {
    FLAVOR_LEGACY: "Hostname",
    FLAVOR_4_8_4: "hostname",
    FLAVOR_CURRENT: "hostname",
}

DRIVER_LABELS = {
    FLAVOR_LEGACY: "DCGM_FI_DRIVER_VERSION",
    FLAVOR_4_8_4: "DCGM_FI_DRIVER_VERSION",
    FLAVOR_CURRENT: "DCGM_FI_SYSTEM_DRIVER_VERSION",
}


def metrics(flavor):
    """Return the list of (name, scale, help, MetricDef) emitted by flavor."""
    result = []
    for metric in CATALOG:
        naming = metric.naming(flavor)
        if naming is None:
            continue
        name, scale, help = naming
        result.append((name, scale, help, metric))
    return result
