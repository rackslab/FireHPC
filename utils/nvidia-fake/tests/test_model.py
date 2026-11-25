# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import random

from firehpc_nvidia_fake.model import UTIL_MAX, UTIL_MIN, GPUModel, JobProfile

RATIOS = [
    "util",
    "memory_util",
    "gr_engine_active",
    "sm_active",
    "sm_occupancy",
    "tensor_active",
    "fp64_active",
    "fp32_active",
    "fp16_active",
    "dram_active",
]


def _run(model, job_id, start, duration, step=1.0):
    now = start
    while now < start + duration:
        model.update(job_id, now)
        now += step
    return now


def _check_ranges(gpu, values):
    for key in RATIOS:
        assert 0.0 <= values[key] <= 1.0, key
    assert (
        values["fb_used"] + values["fb_reserved"] + values["fb_free"]
        == (values["fb_total"])
    )
    assert gpu.power_idle_w <= values["power"] <= gpu.power_max_w


def test_idle(config):
    gpu = config.gpus[0]
    model = GPUModel(gpu, rng=random.Random(1))
    _run(model, None, 0.0, 60.0)
    values = model.values()
    _check_ranges(gpu, values)
    assert values["util"] == 0.0
    assert values["fb_used"] == 0.0
    assert values["power"] == gpu.power_idle_w
    assert values["sm_active"] == 0.0


def test_busy(config):
    gpu = config.gpus[0]
    model = GPUModel(gpu, rng=random.Random(1))
    now = 0.0
    for _ in range(600):
        model.update("42", now)
        now += 1.0
        values = model.values()
        _check_ranges(gpu, values)
        if now > 60:
            # Settled after the ramp up.
            assert UTIL_MIN - 0.01 <= values["util"] <= UTIL_MAX
            assert values["fb_used"] > 0.25 * values["fb_total"]
            assert values["power"] > gpu.power_idle_w + 100


def test_idle_decay_smooth(config):
    gpu = config.gpus[0]
    model = GPUModel(gpu, rng=random.Random(1))
    now = _run(model, "42", 0.0, 120.0)
    previous = model.values()["util"]
    assert previous > UTIL_MIN - 0.01
    for _ in range(30):
        model.update(None, now)
        now += 1.0
        util = model.values()["util"]
        # Decreases without dropping to zero at once.
        assert 0.0 < util < previous
        assert util > previous * 0.7
        previous = util
    _run(model, None, now, 120.0)
    assert model.values()["util"] < 0.001


def test_energy_monotonic(config):
    gpu = config.gpus[0]
    model = GPUModel(gpu, rng=random.Random(1))
    previous = 0.0
    now = 0.0
    for step in range(300):
        model.update("42" if 50 <= step < 200 else None, now)
        now += 1.0
        energy = model.values()["energy"]
        assert energy >= previous
        previous = energy
    # At least idle power during the whole period.
    assert previous >= gpu.power_idle_w * 299


def test_profile_stable_per_job(config):
    uuid = config.gpus[0].uuid
    assert JobProfile("42", uuid).util == JobProfile("42", uuid).util
    assert JobProfile("42", uuid).util != JobProfile("43", uuid).util


def test_new_job_new_profile(config):
    model = GPUModel(config.gpus[0], rng=random.Random(1))
    model.update("42", 0.0)
    first = model.profile
    model.update("43", 1.0)
    assert model.profile is not first
    assert model.profile.job_id == "43"
