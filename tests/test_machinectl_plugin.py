# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of the vendored machinectl Ansible connection plugin, skipped when Ansible
is not installed."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

PLUGIN_PATH = (
    Path(__file__).parent.parent / "lib" / "ansible" / "connections" / "machinectl.py"
)

# Do not let Ansible create its temporary files in user home directory.
_ansible_home = tempfile.mkdtemp(prefix="firehpc-tests-ansible-")
os.environ.setdefault("ANSIBLE_HOME", _ansible_home)
os.environ.setdefault("ANSIBLE_LOCAL_TEMP", os.path.join(_ansible_home, "tmp"))

try:
    import ansible  # noqa: F401
except ImportError:
    plugin = None
else:
    spec = importlib.util.spec_from_file_location("machinectl_plugin", PLUGIN_PATH)
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)

HELPER = ["/usr/bin/firehpc", "--remote", "server", "remote"]
VERSION_OUTPUT = b"systemd 257 (257.9-1)\n"


@unittest.skipIf(plugin is None, "Ansible is not installed")
class TestMachineCtl(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            plugin.subprocess, "check_output", return_value=VERSION_OUTPUT
        )
        self.check_output = patcher.start()
        self.addCleanup(patcher.stop)

    def test_documentation(self):
        options = yaml.safe_load(plugin.DOCUMENTATION)["options"]
        self.assertEqual(
            options["remote_helper"]["vars"],
            [{"name": "ansible_machinectl_remote_helper"}],
        )

    def test_local(self):
        machinectl = plugin.MachineCtl("/usr/bin/machinectl")
        self.assertEqual(machinectl.helper, [])
        self.assertEqual(machinectl.version, "257")
        self.check_output.assert_called_once_with(["/usr/bin/machinectl", "--version"])
        self.assertEqual(
            machinectl.build_command("shell", args=["id"], machine="admin"),
            ["/usr/bin/machinectl", "--setenv=TERM=dumb", "shell", "admin", "id"],
        )

    def test_helper(self):
        machinectl = plugin.MachineCtl(helper=HELPER)
        remote_machinectl = HELPER + [
            "exec",
            "--",
            "env",
            "SYSTEMD_LOG_LEVEL=notice",
            "TERM=dumb",
            "machinectl",
        ]
        self.check_output.assert_called_once_with(remote_machinectl + ["--version"])
        self.assertEqual(
            machinectl.build_command("show", machine="admin"),
            remote_machinectl + ["show", "admin"],
        )

    def test_run_helper(self):
        machinectl = plugin.MachineCtl(helper=HELPER)
        self.check_output.reset_mock(return_value=True)
        self.check_output.return_value = b"/tmp/dir\n"
        self.assertEqual(
            machinectl.run_helper(["exec", "--", "mktemp", "-d"]), b"/tmp/dir\n"
        )
        self.check_output.assert_called_once_with(
            HELPER + ["exec", "--", "mktemp", "-d"], stdin=plugin.subprocess.DEVNULL
        )

    def test_run_helper_error(self):
        machinectl = plugin.MachineCtl(helper=HELPER)
        self.check_output.side_effect = plugin.subprocess.CalledProcessError(1, "x")
        with self.assertRaises(plugin.AnsibleError):
            machinectl.run_helper(["upload", "/src", "/dst"])


@unittest.skipIf(plugin is None, "Ansible is not installed")
class TestConnectionHelperTransfers(unittest.TestCase):
    def setUp(self):
        self.connection = plugin.Connection.__new__(plugin.Connection)
        self.connection.machine = "admin.hpc.john"
        self.connection.machinectl = mock.Mock(helper=HELPER)
        self.connection.machinectl.run_helper.return_value = b"/tmp/tmp.XYZ\n"
        self.connection._run_command = mock.Mock(return_value=(0, b"", b""))

    def helper_calls(self):
        return [c.args[0] for c in self.connection.machinectl.run_helper.call_args_list]

    def test_copy_to(self):
        result = self.connection._helper_copy_to("/local/AnsiballZ_ping.py", "/root/x")
        self.assertEqual(result, (0, b"", b""))
        self.connection._run_command.assert_called_once_with(
            "copy-to",
            args=["/tmp/tmp.XYZ/AnsiballZ_ping.py", "/root/x"],
            machine="admin.hpc.john",
        )
        self.assertEqual(
            self.helper_calls(),
            [
                ["exec", "--", "mktemp", "-d"],
                [
                    "upload",
                    "/local/AnsiballZ_ping.py",
                    "/tmp/tmp.XYZ/AnsiballZ_ping.py",
                ],
                ["exec", "--", "rm", "-rf", "/tmp/tmp.XYZ"],
            ],
        )

    def test_copy_from(self):
        self.connection._helper_copy_from("/etc/hostname", "/local/hostname")
        self.connection._run_command.assert_called_once_with(
            "copy-from",
            args=["/etc/hostname", "/tmp/tmp.XYZ/hostname"],
            machine="admin.hpc.john",
        )
        self.assertEqual(
            self.helper_calls(),
            [
                ["exec", "--", "mktemp", "-d"],
                ["download", "/tmp/tmp.XYZ/hostname", "/local/hostname"],
                ["exec", "--", "rm", "-rf", "/tmp/tmp.XYZ"],
            ],
        )

    def test_copy_from_failure(self):
        self.connection._run_command.return_value = (1, b"", b"error")
        result = self.connection._helper_copy_from("/etc/hostname", "/local/hostname")
        self.assertEqual(result[0], 1)
        self.assertEqual(
            self.helper_calls(),
            [
                ["exec", "--", "mktemp", "-d"],
                ["exec", "--", "rm", "-rf", "/tmp/tmp.XYZ"],
            ],
        )

    def test_cleanup_on_error(self):
        self.connection._run_command.side_effect = RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            self.connection._helper_copy_to("/local/file", "/root/file")
        self.assertEqual(
            self.helper_calls()[-1], ["exec", "--", "rm", "-rf", "/tmp/tmp.XYZ"]
        )
