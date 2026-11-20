# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import io
import json
import logging
import unittest
from unittest import mock

from firehpc.agent import PROTOCOL
from firehpc.agent.client import AgentProvider, AgentSession
from firehpc.agent.server import Agent
from firehpc.errors import FireHPCRuntimeError
from firehpc.version import get_version


def requests(*messages):
    return io.BytesIO(b"".join(json.dumps(msg).encode() + b"\n" for msg in messages))


def responses(writer):
    return [json.loads(line) for line in writer.getvalue().splitlines()]


class TestAgentServer(unittest.TestCase):
    def setUp(self):
        self.provider = mock.Mock()
        self.provider.running.return_value = []
        self.provider.stop.return_value = None
        self.factory = mock.Mock(return_value=self.provider)

    def run_agent(self, *messages):
        writer = io.BytesIO()
        Agent(requests(*messages), writer, self.factory).run()
        return responses(writer)

    def test_hello(self):
        result = self.run_agent()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["hello"]["protocol"], PROTOCOL)

    def test_call(self):
        self.provider.image_exists.return_value = True
        result = self.run_agent(
            {
                "id": 1,
                "provider": "nspawn",
                "cluster": "hpc",
                "method": "image_exists",
                "params": {"name": "debian12"},
            }
        )
        self.factory.assert_called_once_with("nspawn", "hpc")
        self.provider.image_exists.assert_called_once_with(name="debian12")
        self.assertEqual(result[1], {"id": 1, "result": True})

    def test_provider_per_cluster(self):
        self.run_agent(
            {"id": 1, "provider": "nspawn", "cluster": "hpc", "method": "running"},
            {"id": 2, "provider": "nspawn", "cluster": "hpc", "method": "stop"},
            {"id": 3, "provider": "nspawn", "cluster": "other", "method": "running"},
        )
        self.assertEqual(
            self.factory.call_args_list,
            [mock.call("nspawn", "hpc"), mock.call("nspawn", "other")],
        )

    def test_unsupported_method(self):
        result = self.run_agent(
            {"id": 1, "provider": "nspawn", "cluster": "hpc", "method": "__init__"}
        )
        self.assertEqual(result[1], {"id": 1, "error": "Unsupported method __init__"})
        self.factory.assert_not_called()

    def test_provider_error(self):
        self.provider.stop.side_effect = RuntimeError("DBus failure")
        result = self.run_agent(
            {"id": 1, "provider": "nspawn", "cluster": "hpc", "method": "stop"}
        )
        self.assertEqual(result[1], {"id": 1, "error": "DBus failure"})

    def test_unserializable_result(self):
        self.provider.running.return_value = object()
        result = self.run_agent(
            {"id": 1, "provider": "nspawn", "cluster": "hpc", "method": "running"}
        )
        self.assertEqual(result[1]["id"], 1)
        self.assertIn("not JSON serializable", result[1]["error"])

    def test_invalid_json(self):
        writer = io.BytesIO()
        Agent(io.BytesIO(b"not json\n"), writer, self.factory).run()
        result = responses(writer)
        self.assertIsNone(result[1]["id"])
        self.assertIn("error", result[1])

    def test_invalid_params(self):
        result = self.run_agent(
            {
                "id": 1,
                "provider": "nspawn",
                "cluster": "hpc",
                "method": "running",
                "params": [],
            }
        )
        self.assertEqual(
            result[1], {"id": 1, "error": "Request parameters must be an object"}
        )

    def test_unknown_provider(self):
        writer = io.BytesIO()
        Agent(
            requests({"id": 1, "provider": "nope", "cluster": "hpc", "method": "stop"}),
            writer,
        ).run()
        self.assertEqual(
            responses(writer)[1],
            {"id": 1, "error": "Unsupported machine provider nope"},
        )


def agent_output(*messages, hello=True):
    if hello:
        messages = (
            {"hello": {"version": get_version(), "protocol": PROTOCOL}},
        ) + messages
    return io.BytesIO(b"".join(json.dumps(msg).encode() + b"\n" for msg in messages))


class TestAgentSession(unittest.TestCase):
    def test_call_result(self):
        writer = io.BytesIO()
        session = AgentSession(
            "server", agent_output({"id": 1, "result": ["admin"]}), writer
        )
        self.assertEqual(session.call("nspawn", "hpc", "running"), ["admin"])
        self.assertEqual(
            json.loads(writer.getvalue()),
            {
                "id": 1,
                "provider": "nspawn",
                "cluster": "hpc",
                "method": "running",
                "params": {},
            },
        )

    def test_call_error(self):
        session = AgentSession(
            "server", agent_output({"id": 1, "error": "boom"}), io.BytesIO()
        )
        with self.assertRaisesRegex(FireHPCRuntimeError, "server: boom"):
            session.call("nspawn", "hpc", "stop")

    def test_call_logs(self):
        session = AgentSession(
            "server",
            agent_output(
                {
                    "log": {
                        "name": "firehpc.providers.nspawn.dbus",
                        "level": logging.INFO,
                        "msg": "Starting container admin",
                    }
                },
                {"id": 1, "result": None},
            ),
            io.BytesIO(),
        )
        with self.assertLogs("firehpc.providers.nspawn.dbus", level="INFO") as logs:
            self.assertIsNone(
                session.call("nspawn", "hpc", "start", {"names": ["admin"]})
            )
        self.assertEqual(
            logs.output, ["INFO:firehpc.providers.nspawn.dbus:Starting container admin"]
        )

    def test_protocol_mismatch(self):
        reader = agent_output(
            {"hello": {"version": "0", "protocol": PROTOCOL + 1}}, hello=False
        )
        with self.assertRaisesRegex(FireHPCRuntimeError, "protocol"):
            AgentSession("server", reader, io.BytesIO())

    def test_no_hello(self):
        with self.assertRaisesRegex(FireHPCRuntimeError, "Unexpected first message"):
            AgentSession("server", agent_output({"id": 1}, hello=False), io.BytesIO())

    def test_unexpected_termination(self):
        session = AgentSession(
            "server", agent_output(), io.BytesIO(), on_eof=lambda: "agent crashed"
        )
        with self.assertRaisesRegex(
            FireHPCRuntimeError, "terminated unexpectedly: agent crashed"
        ):
            session.call("nspawn", "hpc", "running")


class TestAgentProvider(unittest.TestCase):
    def test_methods(self):
        session = mock.Mock()
        session.call.return_value = True
        provider = AgentProvider(session, "nspawn", "hpc")
        self.assertTrue(provider.image_exists(name="debian12"))
        session.call.assert_called_once_with(
            "nspawn", "hpc", "image_exists", {"name": "debian12"}
        )

    def test_unsupported_method(self):
        with self.assertRaises(AttributeError):
            AgentProvider(mock.Mock(), "nspawn", "hpc").remove_everything

    def test_positional_arguments(self):
        with self.assertRaises(TypeError):
            AgentProvider(mock.Mock(), "nspawn", "hpc").image_exists("debian12")
