# Copyright (c) 2024 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from ClusterShell.NodeSet import NodeSet


class FilterModule:
    def _expand(self, nodes):
        return list(NodeSet(nodes))

    def _fold(self, nodes):
        nodeset = NodeSet()
        for node in nodes:
            nodeset.update(node)
        return str(nodeset)

    def filters(self):
        return {"nodeset_expand": self._expand, "nodeset_fold": self._fold}
