#!/bin/sh
#
# Copyright (c) 2021, Rackslab
#
# GNU General Public License v3.0+

machinectl pull-raw https://hub.nspawn.org/storage/debian/bullseye/raw/image.raw.xz admin

for HOST in front cn1 cn2; do
  machinectl clone admin ${HOST}
done
machinectl list-images

# create directory for home shared by all containers
systemd-run mkdir -p /var/tmp/firehpc/hpc/home

for HOST in admin front cn1 cn2; do
  systemctl start firehpc-container@hpc:${HOST}.service
done

# install python
for HOST in admin front cn1 cn2; do
  machinectl shell ${HOST} /usr/bin/apt install -y python3
done

ansible --connection machinectl all -m ping
ansible-playbook --connection machinectl conf/playbooks/prepare-ssh.yml
ANSIBLE_REMOTE_USER=root ansible-playbook conf/playbooks/site.yml
