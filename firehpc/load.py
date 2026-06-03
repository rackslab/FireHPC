# Copyright (c) 2023-2025 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
import logging
import sys
import json
import random
import time
import threading
from collections import namedtuple
from datetime import datetime

from .settings import RuntimeSettings
from .cluster import EmulatedCluster
from .state import UserState, ClusterState
from .ssh import SSHClient
from .errors import FireHPCRuntimeError

if TYPE_CHECKING:
    from .users import UserEntry

logger = logging.getLogger(__name__)

# 2-tuple of possible jobs timelimits and durations with their correspond weights in
# ramdom selection.
JOBS_TIMELIMITS = (["10", "30", "1:0:0", "6:0:0"], [50, 5, 2, 1])
JOBS_DURATIONS = ([360, 540, 720, 1200], [50, 5, 2, 1])

# Realistic Slurm job names for synthetic load (random choice per submission).
JOB_NAMES = [
    "train_resnet50",
    "pytorch_ddp_epoch",
    "gromacs_npt_equil",
    "openfoam_cavity",
    "dft_scf_relax",
    "variant_call_chr21",
    "hpl_weak_scale",
    "nextflow_rnaseq",
    "jax_pmap_train",
    "mpi_io_bandwidth",
    "tensorflow_benchmark",
    "monte_carlo_sampling",
    "bayesian_mcmc_chain",
    "weather forecast ensemble",
    "finetune bert base",
    "lattice qcd beta 4.2",
    "production_molecular_dynamics_equilibration_extended_300k",
    "weak_scaling_hpl_benchmark_custom_matrix_size_1048576",
    "large_eddy_simulation_turbulent_channel_reynolds_180",
    "distributed_imagenet1k_resnet152_mixed_precision_fp16",
    "ab_initio_molecular_dynamics_car_parrinello_benzene_298k_1fs",
    "multi_node_mpi_io_bandwidth_stripe_16_lustre_ost_rotation",
    "continued equilibration production run restraints off v3",
    "genome wide association study european ancestry batch 07",
    "radiative_hydrodynamics_supernova_remant_post_shock_turb",
    "Train ResNet50 v2",
    "PyTorch DDP Epoch",
    "GROMACS NPT Equilibration",
    "OpenFOAM Cavity Flow",
    "HPL Weak Scaling Benchmark",
    "MD Production Run Stage 2",
    "Nextflow RNAseq Pipeline",
    "WGS Variant Call Chr21",
    "Large Eddy Simulation Channel Re180",
    "Distributed Training ImageNet1k FP16",
    "Ab Initio MD Car Parrinello 298K",
    "Train_ResNet50_Production",
    "PyTorch_DDP_MultiNode",
    "CFD_LES_Channel_Re180",
    "MPI IO Bandwidth Test",
]

ClusterPartition = namedtuple(
    "ClusterPartition",
    [
        "name",
        "nodes",
        "cpus",
        "gpus",
        "gpu_untyped_max",
        "gpu_typed_max",
        "time",
    ],
)


def _accumulate_node_gpu_gres(gres: str) -> Tuple[int, Dict[str, int], int]:
    """Parse one node's Gres= string.

    Returns (total_gpu_count, counts_per_type, untyped_count) for that node.
    Untyped segments look like ``gpu:4``; typed like ``gpu:h100:2``.
    """
    typed: Dict[str, int] = {}
    untyped = 0
    total = 0
    if not gres or not gres.strip():
        return 0, typed, 0
    for segment in gres.split(","):
        parts = segment.strip().split(":")
        if not parts or parts[0] != "gpu":
            continue
        try:
            count = int(parts[-1])
        except ValueError:
            continue
        total += count
        if len(parts) == 2:
            untyped += count
        else:
            gpu_type = parts[1]
            typed[gpu_type] = typed.get(gpu_type, 0) + count
    return total, typed, untyped


def _partition_gpu_totals(
    nodes: list, partition_name: str
) -> Tuple[int, int, Dict[str, int]]:
    """Aggregate GPU GRES for nodes in a partition.

    Returns (gpus_total, max_untyped_per_node, max_typed_per_node_per_type).
    """
    gpus_total = 0
    max_untyped = 0
    max_typed: Dict[str, int] = {}
    for node in nodes:
        if partition_name not in node["partitions"]:
            continue
        gres = node.get("gres") or ""
        if not len(gres):
            continue
        node_total, typed, untyped = _accumulate_node_gpu_gres(gres)
        gpus_total += node_total
        if untyped:
            max_untyped = max(max_untyped, untyped)
        for gpu_type, count in typed.items():
            max_typed[gpu_type] = max(max_typed.get(gpu_type, 0), count)
    return gpus_total, max_untyped, max_typed


def load_clusters(
    settings: RuntimeSettings,
    clusters: List[str],
    user_state: UserState,
    time_off_factor: int,
):
    loaders = []
    threads = []
    try:
        for _cluster in clusters:
            cluster_state = ClusterState(user_state, _cluster)
            loader = ClusterJobsLoader(
                EmulatedCluster(
                    settings, _cluster, cluster_state, cluster_state.load()
                ),
                time_off_factor,
            )
            thread = threading.Thread(target=loader.run)
            loaders.append(loader)
            threads.append(thread)
            thread.start()
        # wait for any thread
        threads[0].join()
    except FireHPCRuntimeError as e:
        logger.critical(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, setting loader stop flag.")
        for loader in loaders:
            loader.stop = True
        logger.info("Waiting for loader threads to stop…")
        for thread in threads:
            thread.join()
        logger.info("Cluster jobs loader is stopped.")


class ClusterJobsLoader:
    def __init__(self, cluster: EmulatedCluster, time_off_factor: int):
        self.cluster = cluster
        self.time_off_factor = time_off_factor
        self.ssh = SSHClient(self.cluster, asbin=False)
        self.stop = False
        # Initialized in run()
        self.select_type = None
        self.accounting = False

    def run(self) -> None:
        logger.info("cluster %s: started running jobs loader", self.cluster.name)
        status = self.cluster.status()

        def random_partition():
            """Select randomly one partition weighted by their number of nodes."""
            return random.choices(
                partitions, [partition.nodes for partition in partitions]
            )[0]

        try:
            self._get_cluster_config()
            partitions = self._get_partitions()
            logger.info(
                "cluster %s: partitions found: %s", self.cluster.name, partitions
            )
            qos = self._get_qos()
            logger.info("cluster %s: QOS found: %s", self.cluster.name, qos)

            while not self.stop:
                active_jobs = self._get_nb_active_jobs()
                active_jobs_limit = self._get_nb_active_jobs_limit(partitions)
                if active_jobs >= active_jobs_limit:
                    logger.debug(
                        "cluster %s: Waiting for jobs to run…",
                        self.cluster.name,
                    )
                    time.sleep(5)
                else:
                    nb_submit = active_jobs_limit - active_jobs
                    logger.info(
                        "cluster %s: %s new jobs to submit",
                        self.cluster.name,
                        nb_submit,
                    )
                    while nb_submit:
                        user = random.choice(status.directory.users)
                        self._launch_job(user, random.choice(qos), random_partition())
                        nb_submit -= 1
        except FireHPCRuntimeError as err:
            logger.critical(
                "cluster %s: emulator thread failed with error: %s",
                self.cluster.name,
                str(err),
            )
        logger.info("cluster %s: jobs loader is stopping", self.cluster.name)

    def _get_cluster_config(self) -> None:
        stdout, stderr = self.ssh.exec(
            [f"admin.{self.cluster.name}", "scontrol", "show", "config"]
        )
        for line in stdout.decode().split("\n"):
            if line.startswith("SelectType "):
                self.select_type = line.split(" = ")[1]
            if (
                line.startswith("AccountingStorageType ")
                and line.split(" = ")[1] == "accounting_storage/slurmdbd"
            ):
                self.accounting = True

    def _get_partitions(self) -> List[ClusterPartition]:
        stdout_partitions, _stderr_p = self.ssh.exec(
            [f"admin.{self.cluster.name}", "scontrol", "show", "partitions", "--json"]
        )
        stdout_nodes, _stderr_n = self.ssh.exec(
            [f"admin.{self.cluster.name}", "scontrol", "show", "nodes", "--json"]
        )
        try:
            partitions = json.loads(stdout_partitions)["partitions"]
            nodes = json.loads(stdout_nodes)["nodes"]
        except json.decoder.JSONDecodeError as err:
            raise FireHPCRuntimeError(
                f"Unable to retrieve partitions or nodes from cluster "
                f"{self.cluster.name}: {str(err)}"
            ) from err
        result = []
        for partition in partitions:
            gpus_total, gpu_untyped_max, gpu_typed_max = _partition_gpu_totals(
                nodes, partition["name"]
            )
            result.append(
                ClusterPartition(
                    partition["name"],
                    partition["nodes"]["total"],
                    partition["cpus"]["total"],
                    gpus_total,
                    gpu_untyped_max,
                    gpu_typed_max,
                    partition["maximums"]["time"],
                )
            )
        return result

    def _get_qos(self) -> list[str]:
        if not self.accounting:
            logger.info(
                "cluster %s: accounting is disabled, skipping QOS retrieval",
                self.cluster.name,
            )
            return [None]
        stdout, stderr = self.ssh.exec(
            [f"admin.{self.cluster.name}", "sacctmgr", "show", "qos", "--json"]
        )
        try:
            qos_output = json.loads(stdout)
            # QOS key has changed to lower case in Slurm 24.05
            qos_key = "qos" if "qos" in qos_output else "QOS"
            return [qos["name"] for qos in json.loads(stdout)[qos_key]]
        except json.decoder.JSONDecodeError as err:
            raise FireHPCRuntimeError(
                f"Unable to retrieve qos from cluster {self.cluster.name}: {str(err)}"
            ) from err

    def _get_nb_active_jobs_limit(self, partitions) -> int:
        """Return the limit number of active jobs on the given partitions."""

        def total_nodes():
            """Return total number of nodes in all partitions."""
            return sum([partition.nodes for partition in partitions])

        # Formula to have jobs limit that grows less than the number of nodes. With
        # this formula, we have:
        #   2 nodes: 12 jobs
        #   10 nodes: 64 jobs
        #   100 nodes: 270 jobs
        #   1000 nodes: 918 jobs
        #
        # It is divided by a time off factor outside business hours to emulate
        # load decrease when humans stop working.

        now = datetime.now()

        time_off_factor = 1
        if now.weekday() > 5 or now.hour > 19 or now.hour < 8:
            time_off_factor = self.time_off_factor

        return int((30 * (total_nodes() ** 0.5) - 30) / time_off_factor)

    def _get_nb_active_jobs(self):
        """Return the current number of active jobs (ie. pending or running) on the
        given partitions."""
        stdout, stderr = self.ssh.exec(
            [
                f"admin.{self.cluster.name}",
                "squeue",
                "--state",
                "pending,running",
                "--json",
            ]
        )
        try:
            return len(json.loads(stdout)["jobs"])
        except json.decoder.JSONDecodeError as err:
            raise FireHPCRuntimeError(
                f"Unable to retrieve active jobs from cluster {self.cluster.name}: "
                f"{str(err)}"
            ) from err

    def _launch_job(
        self, user: UserEntry, qos: Optional[str], partition: ClusterPartition
    ) -> None:
        logger.info(
            "cluster %s: submitting job for user %s on partition %s with QOS %s",
            self.cluster.name,
            user.login,
            partition.name,
            qos,
        )
        # If there is only one container, consider the cluster is using emulator mode
        # and submit job on admin node. Otherwise, submit job on login node.
        if len(self.cluster.status().containers) == 1:
            dest = "admin"
        else:
            dest = "login"
        if partition.time["set"]:
            timelimit = str(partition.time["number"])
        else:
            timelimit = random.choices(JOBS_TIMELIMITS[0], weights=JOBS_TIMELIMITS[1])[
                0
            ]

        # Make 1/10th of job radomly fail.
        script = "/usr/bin/sleep " + str(
            random.choices(JOBS_DURATIONS[0], weights=JOBS_DURATIONS[1])[0]
        )
        if not random.choices([True, False], weights=[10, 1])[0]:
            script += " && /bin/false"

        cmd = [
            f"{user.login}@{dest}.{self.cluster.name}",
            "sbatch",
            "--job-name",
            random.choice(JOB_NAMES),
            "--partition",
            partition.name,
            "--time",
            timelimit,
            "--output",
            "/dev/null",
            "--wrap",
            script,
        ]
        # Insert QOS argument if defined.
        if qos:
            cmd[2:2] = ["--qos", qos]

        def random_power_two(limit: int) -> int:
            """Select randomly one power of two below the limit."""
            i = 1
            possible_values = []
            while i <= limit:
                possible_values.append(i)
                i *= 2
            weights = [
                min(512, 2 ** (len(possible_values) - index[0] - 1))
                for index in enumerate(possible_values)
            ]
            return random.choices(possible_values, weights)[0]

        # If select/linear, allocate a number of nodes, else allocates a number
        # of tasks.
        if self.select_type == "select/linear":
            cmd.extend(["--nodes", str(random_power_two(partition.nodes))])
        elif partition.gpus:
            choices: List[Tuple[str, Optional[str], int]] = []
            weights: List[int] = []
            if partition.gpu_untyped_max > 0:
                choices.append(("untyped", None, partition.gpu_untyped_max))
                weights.append(partition.gpu_untyped_max)
            for gpu_type, limit in partition.gpu_typed_max.items():
                if limit > 0:
                    choices.append(("typed", gpu_type, limit))
                    weights.append(limit)
            if not choices:
                logger.warning(
                    "cluster %s: partition %s has gpus=%s but no schedulable "
                    "GRES caps; falling back to CPU tasks",
                    self.cluster.name,
                    partition.name,
                    partition.gpus,
                )
                cmd.extend(["--ntasks", str(random_power_two(partition.cpus))])
            else:
                picked = random.choices(choices, weights=weights)[0]
                kind, gpu_type, limit = picked
                n_gpus = random_power_two(limit)
                if kind == "untyped":
                    cmd.extend(["--gpus", str(n_gpus)])
                else:
                    cmd.extend(["--gres", f"gpu:{gpu_type}:{n_gpus}"])
        else:
            cmd.extend(["--ntasks", str(random_power_two(partition.cpus))])

        self.ssh.exec(cmd)
