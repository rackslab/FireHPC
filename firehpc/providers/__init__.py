# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Registry of machine providers."""

from __future__ import annotations

from ..errors import FireHPCRuntimeError
from .base import MachineProvider
from .nspawn import NspawnProvider

PROVIDERS: dict[str, type[MachineProvider]] = {
    NspawnProvider.NAME: NspawnProvider,
}

DEFAULT_PROVIDER = NspawnProvider.NAME


def provider_class(kind: str) -> type[MachineProvider]:
    """Return the machine provider class with the given name."""
    try:
        return PROVIDERS[kind]
    except KeyError as err:
        raise FireHPCRuntimeError(f"Unsupported machine provider {kind}") from err
