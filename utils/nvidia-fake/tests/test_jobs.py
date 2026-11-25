# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os

import pytest

from firehpc_nvidia_fake.jobs import gpu_jobs, parse_environ, parse_gpus

from conftest import write_environ


def test_parse_environ():
    assert parse_environ(b"A=1\0B=x=y\0\0broken\0") == {"A": "1", "B": "x=y"}


def test_parse_environ_invalid_utf8():
    assert parse_environ(b"A=\xff\0B=2\0") == {"B": "2"}


def test_parse_gpus():
    assert parse_gpus("0,2, 3") == [0, 2, 3]
    assert parse_gpus("") == []
    assert parse_gpus("x,1") == [1]


def test_gpu_jobs(tmp_path):
    write_environ(tmp_path, 100, {"SLURM_JOB_ID": "42", "SLURM_JOB_GPUS": "0,1"})
    # Several processes of the same job.
    write_environ(tmp_path, 101, {"SLURM_JOB_ID": "42", "SLURM_JOB_GPUS": "0,1"})
    # Fallback on step GPUs.
    write_environ(tmp_path, 200, {"SLURM_JOB_ID": "43", "SLURM_STEP_GPUS": "2"})
    # Job without GPU.
    write_environ(tmp_path, 300, {"SLURM_JOB_ID": "44"})
    # GPUs without job ID.
    write_environ(tmp_path, 400, {"SLURM_JOB_GPUS": "3"})
    # Not a process directory.
    write_environ(tmp_path, "self-like", {"SLURM_JOB_ID": "45", "SLURM_JOB_GPUS": "3"})
    # Kernel thread with empty environ.
    (tmp_path / "500").mkdir()
    (tmp_path / "500" / "environ").write_bytes(b"")
    # Process gone between listing and reading.
    (tmp_path / "600").mkdir()
    assert gpu_jobs(str(tmp_path)) == {0: "42", 1: "42", 2: "43"}


def test_gpu_jobs_job_gpus_preferred(tmp_path):
    write_environ(
        tmp_path,
        100,
        {"SLURM_JOB_ID": "42", "SLURM_JOB_GPUS": "1", "SLURM_STEP_GPUS": "0"},
    )
    assert gpu_jobs(str(tmp_path)) == {1: "42"}


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_gpu_jobs_unreadable(tmp_path):
    directory = write_environ(
        tmp_path, 100, {"SLURM_JOB_ID": "42", "SLURM_JOB_GPUS": "0"}
    )
    (directory / "environ").chmod(0)
    assert gpu_jobs(str(tmp_path)) == {}


def test_gpu_jobs_missing_root(tmp_path):
    assert gpu_jobs(str(tmp_path / "missing")) == {}
