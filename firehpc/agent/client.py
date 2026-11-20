# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Client side of firehpc-agent protocol."""

from __future__ import annotations
import itertools
import json
import logging
import threading
import typing as t

from . import PROTOCOL
from ..errors import FireHPCRuntimeError
from ..providers.base import MachineProvider
from ..version import get_version

if t.TYPE_CHECKING:
    from ..hosts.remote import RemoteHost

logger = logging.getLogger(__name__)


class AgentSession:
    """Session with firehpc-agent running on a remote host."""

    def __init__(
        self,
        name: str,
        reader: t.BinaryIO,
        writer: t.BinaryIO,
        on_eof: t.Optional[t.Callable[[], str]] = None,
        on_close: t.Optional[t.Callable[[], None]] = None,
    ):
        self.name = name
        self.reader = reader
        self.writer = writer
        self.on_eof = on_eof
        self.on_close = on_close
        self.ids = itertools.count(1)
        self.lock = threading.Lock()
        hello = self._read_message()
        if "hello" not in hello:
            raise FireHPCRuntimeError(
                f"Unexpected first message from firehpc-agent on {self.name}: {hello}"
            )
        self.version = hello["hello"].get("version")
        protocol = hello["hello"].get("protocol")
        if protocol != PROTOCOL:
            raise FireHPCRuntimeError(
                f"Unsupported firehpc-agent protocol version {protocol} on remote "
                f"host {self.name} (expected: {PROTOCOL}), FireHPC versions "
                "must be aligned on local and remote hosts"
            )
        if self.version != get_version():
            logger.warning(
                "FireHPC version on remote host %s (%s) differs from local version "
                "(%s)",
                self.name,
                self.version,
                get_version(),
            )
        logger.debug(
            "Connected to firehpc-agent %s on remote host %s", self.version, self.name
        )

    @classmethod
    def start(cls, host: RemoteHost, command: str) -> AgentSession:
        if logging.getLogger("firehpc").getEffectiveLevel() <= logging.DEBUG:
            command += " --debug"
        channel = host.exec_stream(command)
        stderr = channel.makefile_stderr("rb")

        def on_eof():
            channel.close()
            return stderr.read().decode(errors="replace").strip()

        return cls(
            host.label,
            channel.makefile("rb"),
            channel.makefile("wb"),
            on_eof,
            channel.close,
        )

    def _read_message(self) -> dict:
        line = self.reader.readline()
        if not line:
            details = self.on_eof() if self.on_eof else ""
            raise FireHPCRuntimeError(
                f"firehpc-agent on remote host {self.name} terminated unexpectedly"
                + (f": {details}" if details else "")
            )
        try:
            return json.loads(line)
        except json.JSONDecodeError as err:
            raise FireHPCRuntimeError(
                f"Invalid message from firehpc-agent on remote host {self.name}: "
                f"{line!r}"
            ) from err

    def call(
        self,
        provider: str,
        cluster: str,
        method: str,
        params: t.Optional[dict] = None,
    ):
        with self.lock:
            request_id = next(self.ids)
            request = {
                "id": request_id,
                "provider": provider,
                "cluster": cluster,
                "method": method,
                "params": params or {},
            }
            self.writer.write(json.dumps(request).encode() + b"\n")
            self.writer.flush()
            while True:
                message = self._read_message()
                if "log" in message:
                    record = message["log"]
                    logging.getLogger(record.get("name", "firehpc.agent")).log(
                        record.get("level", logging.INFO),
                        "%s",
                        record.get("msg", ""),
                    )
                    continue
                if message.get("id") != request_id:
                    raise FireHPCRuntimeError(
                        f"Unexpected message from firehpc-agent on remote host "
                        f"{self.name}: {message}"
                    )
                if "error" in message:
                    raise FireHPCRuntimeError(
                        f"Remote host {self.name}: {message['error']}"
                    )
                return message.get("result")

    def close(self) -> None:
        if self.on_close:
            self.on_close()


class AgentProvider:
    """Machine provider running on remote host in firehpc-agent. It exposes the
    methods of MachineProvider."""

    def __init__(self, session: AgentSession, kind: str, cluster: str):
        self.session = session
        self.kind = kind
        self.cluster = cluster

    def __getattr__(self, method: str):
        if method not in MachineProvider.METHODS:
            raise AttributeError(method)

        def remote_method(*args, **kwargs):
            if args:
                raise TypeError("Remote provider methods accept keyword arguments only")
            return self.session.call(self.kind, self.cluster, method, kwargs)

        return remote_method
