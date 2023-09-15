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

from typing import Any
import json

from ..cluster import ClusterStatus
from ..users import UserEntry


class GenericJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, ClusterStatus) or isinstance(obj, UserEntry):
            return obj._generic()
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


class JSONDumper:
    @staticmethod
    def dump(obj: Any) -> str:
        return json.dumps(obj, cls=GenericJSONEncoder)
