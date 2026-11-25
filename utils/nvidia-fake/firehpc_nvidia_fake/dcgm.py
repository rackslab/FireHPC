# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""firehpc-dcgm-exporter: fake NVIDIA DCGM exporter.

Serves DCGM metrics of the fake GPUs in Prometheus text format on /metrics.
GPUs allocated to Slurm jobs report activity, the other GPUs are idle.

The exposition text is written directly instead of using prometheus_client,
which appends _total to counter names: the real exporter emits counters such
as DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION without this suffix.
"""

import argparse
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

from . import catalog
from .config import DEFAULT_CONFIG_PATH, FLAVORS, ConfigError, load_config
from .jobs import DEFAULT_PROC_ROOT, gpu_jobs
from .model import GPUModel

DEFAULT_LISTEN = ":9400"
JOBS_CACHE_SECONDS = 1.0
CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def escape_label(value):
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def format_value(value):
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return repr(float(value))


class Exporter:
    def __init__(
        self,
        config,
        flavor=None,
        hostname=None,
        proc_root=DEFAULT_PROC_ROOT,
        clock=time.monotonic,
        rng=None,
    ):
        self.config = config
        self.flavor = flavor or config.flavor
        self.hostname = hostname or socket.gethostname()
        self.proc_root = proc_root
        self.clock = clock
        self.models = [GPUModel(gpu, rng=rng) for gpu in config.gpus]
        self.metrics = catalog.metrics(self.flavor)
        self.lock = threading.Lock()
        self.jobs = {}
        self.jobs_time = None

    def _refresh_jobs(self, now):
        if self.jobs_time is None or now - self.jobs_time >= JOBS_CACHE_SECONDS:
            self.jobs = gpu_jobs(self.proc_root)
            self.jobs_time = now

    def _labels(self, gpu):
        labels = [
            ("gpu", str(gpu.index)),
            ("UUID", gpu.uuid),
            ("pci_bus_id", gpu.pci_bus_id),
            ("device", gpu.device),
            ("modelName", gpu.name),
            (catalog.HOST_LABELS[self.flavor], self.hostname),
            (catalog.DRIVER_LABELS[self.flavor], self.config.driver_version),
        ]
        return ",".join(
            '{}="{}"'.format(key, escape_label(value)) for key, value in labels
        )

    def render(self):
        """Update the simulation and return the metrics text."""
        with self.lock:
            now = self.clock()
            self._refresh_jobs(now)
            values = []
            for model in self.models:
                model.update(self.jobs.get(model.gpu.index), now)
                values.append((self._labels(model.gpu), model.values()))
        lines = []
        for name, scale, help, metric in self.metrics:
            lines.append("# HELP {} {}".format(name, help))
            lines.append("# TYPE {} {}".format(name, metric.kind))
            integer = name in catalog.INTEGER_NAMES
            for labels, quantities in values:
                value = quantities[metric.quantity] * scale
                if integer:
                    value = int(round(value))
                lines.append("{}{{{}}} {}".format(name, labels, format_value(value)))
        return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    exporter = None

    def do_GET(self):
        if self.path.split("?", 1)[0] != "/metrics":
            self.send_error(404)
            return
        body = self.exporter.render().encode()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Do not log every scrape.
        pass


class Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def parse_listen(value):
    host, sep, port = value.rpartition(":")
    if not sep or not port.isdigit():
        raise argparse.ArgumentTypeError(
            "invalid listen address {!r}, expected [host]:port".format(value)
        )
    return host.strip("[]"), int(port)


def make_server(exporter, address):
    handler = type("BoundHandler", (Handler,), {"exporter": exporter})
    return Server(address, handler)


def parser():
    result = argparse.ArgumentParser(
        prog="firehpc-dcgm-exporter",
        description="Fake NVIDIA DCGM exporter for FireHPC emulated GPU nodes",
    )
    result.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Path to fake GPUs configuration file (default: %(default)s)",
    )
    result.add_argument(
        "--listen",
        type=parse_listen,
        default=DEFAULT_LISTEN,
        help="Address to listen on (default: %(default)s)",
    )
    result.add_argument(
        "--flavor",
        choices=FLAVORS,
        help="Metric names to emit, overrides the configuration file",
    )
    result.add_argument(
        "--proc",
        default=DEFAULT_PROC_ROOT,
        help="Root of the proc filesystem (default: %(default)s)",
    )
    return result


def main():
    args = parser().parse_args()
    try:
        config = load_config(args.config)
    except ConfigError as err:
        sys.stderr.write("firehpc-dcgm-exporter: {}\n".format(err))
        sys.exit(1)
    exporter = Exporter(config, flavor=args.flavor, proc_root=args.proc)
    server = make_server(exporter, args.listen)
    sys.stderr.write(
        "firehpc-dcgm-exporter: serving {} GPU(s) with {} flavor on {}:{}\n".format(
            len(config.gpus), exporter.flavor, args.listen[0] or "*", args.listen[1]
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
