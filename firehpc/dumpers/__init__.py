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

from .console import ConsoleDumper
from .json import JSONDumper

from ..errors import FireHPCRuntimeError


class DumperFactory:
    FORMATS = {
        "console": ConsoleDumper,
        "json": JSONDumper,
    }

    @classmethod
    def get(cls, format):
        try:
            return cls.FORMATS[format]
        except KeyError as err:
            raise FireHPCRuntimeError(f"Unsupported dump format {format}") from err
