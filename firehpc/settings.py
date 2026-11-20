# Copyright (c) 2023-2025 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import configparser
import logging
import dataclasses
import os
from pathlib import Path
import typing as t

logger = logging.getLogger(__name__)


class RuntimeSettingsAnsible:
    SECTION = "ansible"

    def __init__(self, config):
        self.path = Path(config.get(self.SECTION, "path"))
        self.args = config.get(self.SECTION, "args")


class RuntimeSettingsOS:
    SECTION = "os"

    def __init__(self, config):
        self.db = Path(config.get(self.SECTION, "db"))
        self.requirements = Path(config.get(self.SECTION, "requirements"))


class RuntimeSettings:
    """Settings from configuration files."""

    VENDOR_PATH = Path("/usr/share/firehpc/firehpc.ini")
    SITE_PATH = Path("/etc/firehpc/firehpc.ini")

    def __init__(self):
        _config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation()
        )
        # read vendor configuration file and override with site specific
        # configuration file
        logger.debug("Loading vendor configuration file %s", self.VENDOR_PATH)
        _config.read_file(open(self.VENDOR_PATH))
        if self.SITE_PATH.exists():
            logger.debug("Loading site specific configuration file %s", self.SITE_PATH)
            _config.read_file(open(self.SITE_PATH))

        self.ansible = RuntimeSettingsAnsible(_config)
        self.os = RuntimeSettingsOS(_config)


def default_preferences_path() -> Path:
    """Returns the default path to the user preferences file, through
    XDG_CONFIG_HOME environment variable if it is set."""
    return (
        Path(os.getenv("XDG_CONFIG_HOME", "~/.config")).expanduser()
        / "firehpc"
        / "firehpc.ini"
    )


class UserPreferences:
    """User preferences from optional user configuration file."""

    DEFAULT_AGENT = "firehpc-agent"

    def __init__(self, path: t.Optional[Path] = None):
        if path is None:
            path = default_preferences_path()
        self.path = path
        _config = configparser.ConfigParser()
        if self.path.exists():
            logger.debug("Loading user preferences file %s", self.path)
            with open(self.path) as fh:
                _config.read_file(fh)
        self.remote_host: t.Optional[str] = (
            _config.get("remote", "host", fallback=None) or None
        )
        self.remote_agent: str = _config.get(
            "remote", "agent", fallback=self.DEFAULT_AGENT
        )


REMOTE_ENV_VAR = "FIREHPC_REMOTE"


def explicit_remote(args) -> t.Optional[str]:
    """Return the remote host explicitly requested with command line arguments or
    environment variable, or None. An empty string means local host has been
    explicitly requested."""
    if getattr(args, "local", False):
        return ""
    if getattr(args, "remote", None):
        return args.remote
    return os.getenv(REMOTE_ENV_VAR)


def resolve_remote(args, preferences: UserPreferences) -> t.Optional[str]:
    """Return the remote host to use for new clusters, with the following
    precedence: command line arguments, environment variable, user preferences.
    Returns None when local host must be used."""
    remote = explicit_remote(args)
    if remote is None:
        remote = preferences.remote_host
    return remote or None


def optional_absolute_path(path: t.Optional[t.Union[Path, str]]) -> t.Optional[Path]:
    if path is None:
        return None
    if isinstance(path, str):
        path = Path(path)
    return path.absolute()


def optional_path(path: t.Optional[str]) -> t.Optional[Path]:
    if path is None:
        return None
    return Path(path)


@dataclasses.dataclass
class ClusterRacksDBSettings:
    db: t.Optional[Path] = None
    schema: t.Optional[Path] = None

    @classmethod
    def deserialize(cls, content: t.Optional[dict[str, str]]):
        if not content:
            return cls()
        return cls(
            optional_absolute_path(content.get("db")),
            optional_absolute_path(content.get("schema")),
        )

    def update_from_args(self, args):
        if args.db:
            self.db = optional_absolute_path(args.db)
        if args.schema:
            self.schema = optional_absolute_path(args.schema)

    def serialize(self):
        if self.db is None and self.schema is None:
            return None
        result = {}
        if self.db:
            result["db"] = str(self.db)
        if self.schema:
            result["schema"] = str(self.schema)
        return result


@dataclasses.dataclass
class ClusterSettings:
    os: str
    environment: str
    slurm_emulator: bool
    racksdb: ClusterRacksDBSettings
    custom: t.Optional[Path] = None
    remote: t.Optional[str] = None

    @classmethod
    def from_values(
        cls,
        os: str,
        environment: str,
        slurm_emulator: bool,
        db: t.Optional[t.Union[Path, str]] = None,
        schema: t.Optional[t.Union[Path, str]] = None,
        custom: t.Optional[t.Union[Path, str]] = None,
        remote: t.Optional[str] = None,
    ):
        return cls(
            os,
            environment,
            slurm_emulator,
            ClusterRacksDBSettings(
                optional_absolute_path(db), optional_absolute_path(schema)
            ),
            optional_absolute_path(custom),
            remote or None,
        )

    @classmethod
    def deserialize(cls, content: dict[str, t.Any]):
        return cls(
            content["os"],
            content["environment"],
            content["slurm_emulator"],
            ClusterRacksDBSettings.deserialize(content.get("racksdb")),
            optional_absolute_path(content.get("custom")),
            content.get("remote") or None,
        )

    def update_from_args(self, args):
        self.slurm_emulator = args.slurm_emulator
        if args.custom:
            self.custom = optional_absolute_path(args.custom)
        self.racksdb.update_from_args(args)

    def serialize(self):
        result = {
            "os": self.os,
            "environment": self.environment,
            "slurm_emulator": self.slurm_emulator,
        }
        racksdb = self.racksdb.serialize()
        if racksdb:
            result["racksdb"] = racksdb
        if self.custom:
            result["custom"] = str(self.custom)
        if self.remote:
            result["remote"] = self.remote
        return result
