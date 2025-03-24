# Copyright (c) 2023-2025 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

try:
    from importlib import metadata
except ImportError:
    # On Python < 3.8, use external backport library importlib-metadata.
    import importlib_metadata as metadata


def get_version():
    return metadata.version("firehpc")
