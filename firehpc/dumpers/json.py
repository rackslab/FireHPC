# Copyright (c) 2023-2024 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
