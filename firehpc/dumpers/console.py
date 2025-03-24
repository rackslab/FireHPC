# Copyright (c) 2023-2025 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from typing import TYPE_CHECKING, Any

from ..cluster import ClusterStatus
from ..errors import FireHPCRuntimeError

if TYPE_CHECKING:
    from ..users import UserEntry, GroupEntry
    from ..settings import ClusterSettings


class UserEntryConsoleDumper:
    @staticmethod
    def dump(obj: UserEntry) -> str:
        return f"{obj.login:15s} ({obj.firstname} {obj.lastname})"


class GroupEntryConsoleDumper:
    @staticmethod
    def dump(obj: GroupEntry) -> str:
        return (
            f"{obj.name:15s}: [parent: {obj.parent}]\n"
            f"    members: {', '.join([member.login for member in obj.members])}"
        )


class ClusterSettingsConsoleDumper:
    @staticmethod
    def dump(obj: ClusterSettings):
        result = ""

        def label(name):
            return f"  {name:15s}"

        result += f"{label('os')}: {obj.os}\n"
        result += f"{label('environment')}: {obj.environment}\n"
        if obj.custom:
            result += f"{label('custom')}: {obj.custom}\n"
        result += (
            f"{label('slurm emulator')}: {'yes' if obj.slurm_emulator else 'no'}\n"
        )
        if obj.racksdb.db:
            result += f"{label('db')}: {obj.racksdb.db}\n"
        if obj.racksdb.schema:
            result += f"{label('schema')}: {obj.racksdb.schema}\n"
        return result


class ClusterStatusConsoleDumper:
    @staticmethod
    def dump(obj: ClusterStatus) -> str:
        result = ""

        # List of containers
        result += "containers:\n"
        for container in obj.containers:
            result += f"  {container.name} is running\n"

        # Cluster settings
        result += "settings:\n"
        result += ClusterSettingsConsoleDumper.dump(obj.settings)

        # List of users
        result += "users:\n"
        for user in obj.directory:
            result += f"  {UserEntryConsoleDumper.dump(user)}\n"

        # List of groups
        result += "groups:\n"
        for group in obj.directory.groups:
            result += f"  {GroupEntryConsoleDumper.dump(group)}\n"
        return result


class ConsoleDumper:
    @staticmethod
    def dump(obj: Any) -> str:
        if isinstance(obj, ClusterStatus):
            return ClusterStatusConsoleDumper.dump(obj)
        raise FireHPCRuntimeError(f"Unsupported type {type(obj)} to dump on console")
