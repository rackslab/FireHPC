# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""firehpc-agent runs machine providers on a host on behalf of firehpc running on
another host. firehpc starts the agent through SSH and exchanges JSON messages
separated by newlines on its standard input and output:

- the agent first sends {"hello": {"version": …, "protocol": …}},
- firehpc sends requests {"id", "provider", "cluster", "method", "params"},
- the agent replies {"id", "result"} or {"id", "error"}, possibly preceded by log
  records {"log": {"name", "level", "msg"}}."""

# Version of the protocol between firehpc and firehpc-agent. It must be incremented
# for every incompatible change.
PROTOCOL = 1
