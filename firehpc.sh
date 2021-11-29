#!/bin/sh
#
# Copyright (c) 2021, Rackslab
#
# GNU General Public License v3.0+

if [ -z $1 ]; then
  echo "usage: $0 ZONE"
  exit 1
fi

ZONE=$1
LOCAL=local/$ZONE

machinectl pull-raw https://hub.nspawn.org/storage/debian/bullseye/raw/image.raw.xz admin.${ZONE}

for HOST in login cn1 cn2; do
  machinectl clone admin.${ZONE} ${HOST}.${ZONE}
done
machinectl list-images

# create directory for home shared by all containers
systemd-run mkdir -p /var/tmp/firehpc/${ZONE}/home

for HOST in admin login cn1 cn2; do
  systemctl start firehpc-container@${ZONE}:${HOST}.service
done

# wait a little to ensure network is ready in containers
sleep 2

# install python
for HOST in admin login cn1 cn2; do
  machinectl shell ${HOST}.${ZONE} /usr/bin/apt install -y python3
done

# generate ansible configuration file and inventory
mkdir -p ${LOCAL}
sed "s|%LOCAL%|${LOCAL}|g" conf/ansible.cfg.tpl > ${LOCAL}/ansible.cfg
sed "s|%ZONE%|${ZONE}|g" conf/hosts.tpl > ${LOCAL}/hosts
ln -s ../../conf/group_vars ${LOCAL}/group_vars

export ANSIBLE_CONFIG=${LOCAL}/ansible.cfg

ansible --connection machinectl all -m ping
ansible-playbook conf/playbooks/bootstrap.yml
ansible-playbook conf/playbooks/site.yml
