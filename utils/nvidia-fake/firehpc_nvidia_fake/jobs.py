# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Find the GPUs allocated to Slurm jobs on the node.

The CEEMS exporter reads SLURM_JOB_GPUS (falling back to SLURM_STEP_GPUS) in
the environment of job processes. This module uses the same source, so that
the GPUs reported busy by the fake DCGM exporter are the ones CEEMS assigns
to jobs.
"""

import os

DEFAULT_PROC_ROOT = "/proc"


def parse_environ(data):
    """Parse the content of /proc/<pid>/environ into a dict."""
    result = {}
    for item in data.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        try:
            result[key.decode()] = value.decode()
        except UnicodeDecodeError:
            continue
    return result


def parse_gpus(value):
    """Return the GPU indexes in a SLURM_JOB_GPUS value such as "0,2"."""
    result = []
    for item in value.split(","):
        item = item.strip()
        if item.isdigit():
            result.append(int(item))
    return result


def gpu_jobs(proc_root=DEFAULT_PROC_ROOT):
    """Return a dict of GPU index to Slurm job ID for the GPUs in use."""
    result = {}
    try:
        entries = os.listdir(proc_root)
    except OSError:
        return result
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(os.path.join(proc_root, entry, "environ"), "rb") as fh:
                data = fh.read()
        except OSError:
            # Process gone or not readable.
            continue
        environ = parse_environ(data)
        job_id = environ.get("SLURM_JOB_ID")
        gpus = environ.get("SLURM_JOB_GPUS") or environ.get("SLURM_STEP_GPUS")
        if not job_id or not gpus:
            continue
        for index in parse_gpus(gpus):
            result[index] = job_id
    return result
