# Copyright (c) 2025 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path
import tempfile

from firehpc.state import os_used_by_clusters
from firehpc.state import UserState, ClusterState
from firehpc.settings import ClusterSettings, ClusterRacksDBSettings


class TestClusterHelpers(unittest.TestCase):
    def _save_cluster(self, user_state, cluster, os):
        state = ClusterState(user_state, cluster)
        state.create()
        state.save(
            ClusterSettings(
                os=os,
                environment="ansible-latest",
                slurm_emulator=False,
                racksdb=ClusterRacksDBSettings(),
            )
        )

    def test_os_used_by_clusters(self):
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            user_state = UserState(tmp)
            user_state.create()
            self._save_cluster(user_state, "hpc", "debian13")
            self._save_cluster(user_state, "test", "debian12")

            self.assertTrue(os_used_by_clusters(user_state, "debian13"))
            self.assertTrue(os_used_by_clusters(user_state, "debian12"))
            self.assertFalse(os_used_by_clusters(user_state, "rocky9"))

    def test_os_used_by_clusters_exclude(self):
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            user_state = UserState(tmp)
            user_state.create()
            self._save_cluster(user_state, "hpc", "debian13")

            self.assertFalse(os_used_by_clusters(user_state, "debian13", exclude="hpc"))
            self.assertTrue(
                os_used_by_clusters(user_state, "debian13", exclude="other")
            )
