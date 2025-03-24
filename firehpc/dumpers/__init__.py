# Copyright (c) 2023-2024 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
