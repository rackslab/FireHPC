#!/bin/bash
#
# Copyright (c) 2021, Rackslab
#
# GNU General Public License v3.0+

echo "Powering off the containers"
for HOST in admin front cn1 cn2; do
  machinectl poweroff ${HOST}
done

echo "Waiting for containers to poweroff"
sleep 5

echo "Removing container images"
for HOST in admin front cn1 cn2; do
  machinectl remove ${HOST}
done

# Remove directory shared between containers
systemd-run rm -rf /var/tmp/firehpc
