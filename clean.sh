#!/bin/bash
#
# Copyright (c) 2021, Rackslab
#
# GNU General Public License v3.0+

if [ -z $1 ]; then
  echo "usage: $0 ZONE"
  exit 1
fi

ZONE=$1
LOCAL="local/${ZONE}"

echo "Powering off the containers"
for HOST in admin login cn1 cn2; do
  machinectl poweroff ${HOST}.${ZONE}
done

echo "Waiting for containers to poweroff"
sleep 5

echo "Removing container images"
for HOST in admin login cn1 cn2; do
  machinectl remove ${HOST}.${ZONE}
done

# Remove directory shared between containers
systemd-run rm -rf /var/tmp/firehpc/${ZONE}

rm -rf ${LOCAL}
