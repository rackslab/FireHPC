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

Authorize the `sudo` group to manage containers and images without prompting
for password by deploying this polkit policy file:

```
sudo install -m644 etc/polkit/firehpc.pkla /etc/polkit-1/localauthority/10-vendor.d/10-firehpc.pkla
```

Install FireHPC container service template:

```
sudo install -m644 etc/system/firehpc-container@.service /etc/systemd/system/firehpc-container@.service
```

Install `systemd-nspawn` wrapper:

```
sudo install -m755 lib/exec/firehpc-wrapper /usr/libexec/firehpc-wrapper 
```

NOTE: There might be a bug with `systemd-machined` actions default polkit policy
relying on `auth_admin_keep` permission, see TODO.md for details.

NOTE: Unfortunately, Debian/Ubuntu do not distribute recent versions of polkit
with support of Javascript rules files. The provided `*.pkla` file does not
setup fine-grained permissions for FireHPC made possible with polkit Javascript
rules. In particular, all members of the _sudo_ group have the permissions to
manage all system units, this is not great.

Import [hub.nspawn.org](https://hub.nspawn.org) GPG key in `systemd-importd`
keyring:

```
curl https://hub.nspawn.org/storage/masterkey.pgp -o /tmp/masterkey.nspawn.org
sudo gpg --no-default-keyring --keyring=/etc/systemd/import-pubring.gpg --import /tmp/masterkey.nspawn.org
```

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
ssh -o UserKnownHostsFile=ssh/known_hosts -I ssh/id_rsa root@admin
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
