# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Server side of firehpc-agent protocol, the firehpc-agent program."""

from __future__ import annotations
import argparse
import json
import logging
import os
import sys
import threading
import typing as t

from . import PROTOCOL
from ..providers import provider_class
from ..providers.base import MachineProvider
from ..version import get_version

logger = logging.getLogger(__name__)


def default_provider_factory(kind: str, cluster: str) -> MachineProvider:
    return provider_class(kind)(cluster)


class AgentLogHandler(logging.Handler):
    """Send log records to firehpc on the other side of the protocol."""

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent = agent

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.agent.send(
                {
                    "log": {
                        "name": record.name,
                        "level": record.levelno,
                        "msg": record.getMessage(),
                    }
                }
            )
        except Exception:
            self.handleError(record)


class Agent:
    def __init__(
        self,
        reader: t.BinaryIO,
        writer: t.BinaryIO,
        provider_factory: t.Callable[
            [str, str], MachineProvider
        ] = default_provider_factory,
    ):
        self.reader = reader
        self.writer = writer
        self.provider_factory = provider_factory
        self.providers = {}
        # Log records can be emitted by threads, protect writer with a lock.
        self.lock = threading.Lock()

    def send(self, message: dict) -> None:
        self.write(json.dumps(message).encode() + b"\n")

    def write(self, data: bytes) -> None:
        with self.lock:
            self.writer.write(data)
            self.writer.flush()

    def provider(self, kind: str, cluster: str) -> MachineProvider:
        if (kind, cluster) not in self.providers:
            self.providers[(kind, cluster)] = self.provider_factory(kind, cluster)
        return self.providers[(kind, cluster)]

    def handle(self, line: bytes) -> None:
        request_id = None
        try:
            request = json.loads(line)
            request_id = request.get("id")
            method = request.get("method")
            if method not in MachineProvider.METHODS:
                raise ValueError(f"Unsupported method {method}")
            params = request.get("params")
            if params is None:
                params = {}
            if not isinstance(params, dict):
                raise ValueError("Request parameters must be an object")
            provider = self.provider(
                request.get("provider", ""), request.get("cluster", "")
            )
            result = getattr(provider, method)(**params)
            # Serialize response in try block to report results that cannot be
            # serialized as errors.
            response = json.dumps({"id": request_id, "result": result})
        except Exception as err:
            logger.debug("Error while handling request %s: %s", request_id, err)
            self.send({"id": request_id, "error": str(err) or type(err).__name__})
        else:
            self.write(response.encode() + b"\n")

    def run(self) -> None:
        self.send({"hello": {"version": get_version(), "protocol": PROTOCOL}})
        for line in self.reader:
            if line.strip():
                self.handle(line)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run FireHPC machine providers on behalf of remote firehpc."
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Keep a private copy of standard output for the protocol and redirect file
    # descriptor 1 to standard error, so that anything else printed on standard
    # output cannot corrupt the protocol.
    writer = os.fdopen(os.dup(sys.stdout.fileno()), "wb")
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())

    agent = Agent(sys.stdin.buffer, writer)
    firehpc_logger = logging.getLogger("firehpc")
    firehpc_logger.setLevel(logging.DEBUG if args.debug else logging.INFO)
    firehpc_logger.addHandler(AgentLogHandler(agent))
    firehpc_logger.propagate = False
    try:
        agent.run()
    except KeyboardInterrupt:
        pass
