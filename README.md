# FireHPC: Instantly fire up container-based emulated HPC cluster

## Description

FireHPC is a tool designed to quickly start and setup a tiny emulated HPC
cluster based on Linux containers, ready to run non-intensive MPI jobs with
[Slurm](https://slurm.schedmd.com/overview.html).

Obviously, FireHPC does not aim at performances as you get better performances
out of your computer without containers overhead.

The purposes are the following:

- Setup development, CI and tests environment
- Learn tools and software in breakable environment
- Testing and discovering new technologies in isolated environment

FireHPC aims to emulate HPC clusters with multiple distributions.

## Architecture

FireHPC relies on:

- [`systemd-nspawn`](https://www.freedesktop.org/software/systemd/man/systemd-nspawn.html) containers controlled with `systemd-{networkd,machined}`
- [Ansible](https://docs.ansible.com/ansible/latest/index.html) automation tool

FireHPC also requires the following community Ansible collections:

- [community.general](https://docs.ansible.com/ansible/latest/collections/community/general/index.html) >= 3.8.1
- [community.crypto](https://docs.ansible.com/ansible/latest/collections/community/crypto/index.html)
- [community.mysql] (https://docs.ansible.com/ansible/latest/collections/community/mysql/index.html)

They may not be installed within Ansible on your distribution. In this case,
you can install on your system using `ansible-galaxy`.

## Status

FireHPC is currently an ugly prototype, it is not ready to be used by anyone
except its developper. **Use it at your own risk!**

## Quickstart

On Ubuntu 21.10, start and enable `systemd-networkd` service with _root_
permissions:

```
sudo systemctl start systemd-networkd.service
sudo systemctl enable systemd-networkd.service
```

Restart systemd-resolvd and NetworkManager to get back DNS:

```
sudo systemctl restart systemd-resolvd.service
sudo systemctl restart NetworkManager.service
```

Import [hub.nspawn.org](https://hub.nspawn.org) GPG key in `systemd-importd`
keyring:

```
curl https://hub.nspawn.org/storage/masterkey.pgp -o /tmp/masterkey.nspawn.org
sudo gpg --no-default-keyring --keyring=/etc/systemd/import-pubring.gpg --import /tmp/masterkey.nspawn.org
```

Run installation script:

```
sudo ./install.sh
```

**NOTE:** Please refer to comments in the [install](install.sh) script to get
full details about installed files.


Then, with your regular user, run FireHPC:

```
./firehpc.sh
```

You can connect to your containers (eg. _admin_) with this command:

```
machinectl shell admin
```

Or using SSH with this command:

```
ssh -o UserKnownHostsFile=ssh/known_hosts -I local/ssh/id_rsa root@admin
```

When you are done, you can clean up everything with this command:


```
./clean.sh
```

## Authors

FireHPC is developped by [Rackslab](https://rackslab.io).

## License

FireHPC is distributed under the terms of the GNU General Public License v3.0 or
later (GPLv3+).
