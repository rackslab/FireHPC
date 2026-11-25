# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Simulated activity of a fake GPU.

A GPU allocated to a job follows a bounded random walk around a workload
profile drawn from the job ID, so values look stable during a job and differ
between jobs. A GPU without job decays smoothly towards idle values.

Quantities are kept in base units: ratios in [0, 1], bytes, watts, joules,
hertz and degrees Celsius. The metric catalog converts them to the units of
each DCGM exporter flavor.
"""

import math
import random

# Time constants (seconds) of the exponential smoothing towards targets.
TAU_LOAD = 5.0
TAU_MEMORY = 3.0
TAU_TEMPERATURE = 30.0

# Busy GPU utilization bounds.
UTIL_MIN = 0.40
UTIL_MAX = 1.0
# Standard deviation of the random walk per sqrt(second).
WALK_SIGMA = 0.03
WALK_BOUND = 0.25

IDLE_TEMPERATURE = 30.0
MAX_TEMPERATURE_RISE = 50.0
MEMORY_TEMPERATURE_OFFSET = 4.0
SM_CLOCK_IDLE_HZ = 345e6
SM_CLOCK_MAX_HZ = 1980e6
MEMORY_CLOCK_HZ = 2619e6
FB_RESERVED_RATIO = 0.006


def _clamp(value, low, high):
    return max(low, min(high, value))


class JobProfile:
    """Workload characteristics of a job on a GPU."""

    def __init__(self, job_id, gpu_uuid):
        # String seeds are hashed with SHA-512, the profile is stable across
        # runs and Python versions.
        rng = random.Random("{}:{}".format(job_id, gpu_uuid))
        self.job_id = job_id
        self.util = rng.uniform(0.55, 0.95)
        self.sm_ratio = rng.uniform(0.85, 0.98)
        self.occupancy = rng.uniform(0.25, 0.70)
        self.tensor = rng.uniform(0.10, 0.70)
        self.fp64 = rng.uniform(0.0, 0.30)
        self.fp32 = rng.uniform(0.20, 0.60)
        self.fp16 = rng.uniform(0.05, 0.50)
        self.dram = rng.uniform(0.30, 0.80)
        self.fb = rng.uniform(0.30, 0.90)
        self.pcie_tx = rng.uniform(0.5e9, 4e9)
        self.pcie_rx = rng.uniform(0.5e9, 4e9)
        self.nvlink_tx = rng.uniform(0, 20e9)
        self.nvlink_rx = rng.uniform(0, 20e9)


class GPUModel:
    """State of one simulated GPU."""

    def __init__(self, gpu, rng=None):
        self.gpu = gpu
        self.rng = rng if rng is not None else random.Random()
        self.job_id = None
        self.profile = None
        self.walk = 0.0
        self.last_time = None
        self.util = 0.0
        self.fb_used = 0.0
        self.power = gpu.power_idle_w
        self.temperature = IDLE_TEMPERATURE
        self.energy = 0.0

    @staticmethod
    def _alpha(dt, tau):
        return 1.0 - math.exp(-dt / tau)

    def update(self, job_id, now):
        """Advance the simulation to time now (seconds), with job_id the job
        holding the GPU, or None."""
        dt = 0.0 if self.last_time is None else max(0.0, now - self.last_time)
        self.last_time = now
        # Energy uses the power during the elapsed interval.
        self.energy += self.power * dt

        if job_id != self.job_id:
            self.job_id = job_id
            self.walk = 0.0
            if job_id is not None:
                self.profile = JobProfile(job_id, self.gpu.uuid)
            # On job end, keep the last profile so that ratios derived from
            # utilization decay smoothly.

        if self.job_id is not None:
            self.walk = _clamp(
                self.walk + self.rng.gauss(0.0, WALK_SIGMA * math.sqrt(dt)),
                -WALK_BOUND,
                WALK_BOUND,
            )
            util_target = _clamp(self.profile.util + self.walk, UTIL_MIN, UTIL_MAX)
            fb_target = self.profile.fb * self.gpu.memory_bytes
        else:
            util_target = 0.0
            fb_target = 0.0

        self.util += (util_target - self.util) * self._alpha(dt, TAU_LOAD)
        self.fb_used += (fb_target - self.fb_used) * self._alpha(dt, TAU_MEMORY)
        span = self.gpu.power_max_w - self.gpu.power_idle_w
        self.power = self.gpu.power_idle_w + span * 0.95 * self.util
        temperature_target = IDLE_TEMPERATURE + MAX_TEMPERATURE_RISE * (
            (self.power - self.gpu.power_idle_w) / span
        )
        self.temperature += (temperature_target - self.temperature) * self._alpha(
            dt, TAU_TEMPERATURE
        )

    def _profile_ratio(self, name):
        if self.profile is None:
            return 0.0
        return _clamp(getattr(self.profile, name) * self.util, 0.0, 1.0)

    def values(self):
        """Return the current quantities in base units."""
        total = float(self.gpu.memory_bytes)
        # Framebuffer sizes are whole MiB, so MiB and bytes values are both
        # integers.
        mib = 2**20
        reserved = math.floor(total * FB_RESERVED_RATIO / mib) * mib
        used = math.floor(_clamp(self.fb_used, 0.0, total - reserved) / mib) * mib
        sm_active = self._profile_ratio("sm_ratio")
        if self.profile is not None:
            nvlink_tx = self.profile.nvlink_tx * self.util
            nvlink_rx = self.profile.nvlink_rx * self.util
            pcie_tx = self.profile.pcie_tx * self.util
            pcie_rx = self.profile.pcie_rx * self.util
        else:
            nvlink_tx = nvlink_rx = pcie_tx = pcie_rx = 0.0
        power_jitter = self.rng.uniform(-0.02, 0.02) * self.gpu.power_max_w * self.util
        return {
            "util": _clamp(self.util, 0.0, 1.0),
            "memory_util": self._profile_ratio("dram"),
            "enc_util": 0.0,
            "dec_util": 0.0,
            "gr_engine_active": _clamp(self.util, 0.0, 1.0),
            "sm_active": sm_active,
            "sm_occupancy": _clamp(
                sm_active * (self.profile.occupancy if self.profile else 0.0), 0.0, 1.0
            ),
            "tensor_active": self._profile_ratio("tensor"),
            "fp64_active": self._profile_ratio("fp64"),
            "fp32_active": self._profile_ratio("fp32"),
            "fp16_active": self._profile_ratio("fp16"),
            "dram_active": self._profile_ratio("dram"),
            "fb_total": total,
            "fb_used": float(used),
            "fb_reserved": float(reserved),
            "fb_free": total - used - reserved,
            "power": self.power,
            "power_instant": max(0.0, self.power + power_jitter),
            "energy": self.energy,
            "gpu_temp": self.temperature,
            "memory_temp": self.temperature + MEMORY_TEMPERATURE_OFFSET,
            "sm_clock": SM_CLOCK_IDLE_HZ
            + (SM_CLOCK_MAX_HZ - SM_CLOCK_IDLE_HZ) * min(1.0, self.util * 1.5),
            "memory_clock": MEMORY_CLOCK_HZ,
            "pcie_tx": pcie_tx,
            "pcie_rx": pcie_rx,
            "nvlink_tx": nvlink_tx,
            "nvlink_rx": nvlink_rx,
            "nvlink_total": nvlink_tx + nvlink_rx,
            "zero": 0.0,
        }
