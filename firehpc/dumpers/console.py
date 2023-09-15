#!/usr/bin/env python3
#
# Copyright (C) 2023 Rackslab
#
# This file is part of FireHPC.
#
# FireHPC is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# FireHPC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with FireHPC.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations
from typing import TYPE_CHECKING, Any

from ..cluster import ClusterStatus

if TYPE_CHECKING:
    from ..users import UserEntry


class UserEntryConsoleDumper:
    @staticmethod
    def dump(obj: UserEntry) -> str:
        return f"{obj.login:15s} ({obj.firstname} {obj.lastname})"


class ClusterStatusConsoleDumper:
    @staticmethod
    def dump(obj: ClusterStatus) -> str:
        result = ""
        result += "containers:\n"
        for container in obj.containers:
            result += f"  {container.name} is running\n"
        result += "users:\n"
        for user in obj.users:
            result += f"  {UserEntryConsoleDumper.dump(user)}\n"
        return result


class ConsoleDumper:
    @staticmethod
    def dump(obj: Any) -> str:
        if isinstance(obj, ClusterStatus):
            return ClusterStatusConsoleDumper.dump(obj)
