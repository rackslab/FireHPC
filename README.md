# FireHPC: Instantly fire up container-based emulated HPC cluster

## Description

FireHPC is a tool designed to quickly start and setup a tiny emulated HPC
cluster based on Linux containers.

The purposes are the following:

- Setup development, CI and tests environment
- Learn tools and software in breakable environment
- Testing and discovering new technologies in isolated environment

FireHPC aims to emulate HPC clusters with multiple distributions.

## Architecture

FireHPC relies on:

- [`systemd-nspawn`](https://www.freedesktop.org/software/systemd/man/systemd-nspawn.html) containers controlled with `systemd-{networkd,machined}`
- [Ansible](https://docs.ansible.com/ansible/latest/index.html) automation tool

## Status

FireHPC is currently an ugly prototype, it is not ready to be used by anyone
except its developper. **Use it at your own risk!**

## Quickstart

On Ubuntu 21.10, first start and enable `systemd-networkd`:

```
systemctl start systemd-networkd.service
systemctl enable systemd-networkd.service
```

Restart systemd-resolvd and NetworkManager to get back DNS:

```
systemctl restart systemd-resolvd.service
systemctl restart NetworkManager.service
```

Download `machinectl` Ansible connection plugin from @tomeon:

```
mkdir conf/connections
wget https://github.com/tomeon/ansible-connection-machinectl/raw/master/connection_plugins/machinectl.py \
  -O conf/connections/machinectl.py
```

Import [hub.nspawn.org](https://hub.nspawn.org) GPG key in `systemd-importd`
keyring:

```
curl https://hub.nspawn.org/storage/masterkey.pgp -o /tmp/masterkey.nspawn.org
sudo gpg --no-default-keyring --keyring=/etc/systemd/import-pubring.gpg --import /tmp/masterkey.nspawn.org
```

Run FireHPC as _root_:

```
sudo -E ./firehpc.sh
```

You can connect to your containers (eg. _admin_) with this command:

```
machinectl shell admin
```

When you are done, you can clean up everything with this command:


```
sudo -E ./clean.sh
```

## Authors

FireHPC is developped by [Rackslab](https://rackslab.io).

## License

FireHPC is distributed under the terms of the GNU General Public License v3.0 or
later (GPLv3+).
