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

FireHPC aims to emulate HPC clusters with multiple distributions. It supports
running multiple emulated HPC clusters in parallel on the same host, each
cluster running in its dedicated zone.

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

Install `firehpc`:

```
$ sudo apt install firehpc
```

Add your user in `firehpc` system group:

```
$ sudo usermod -a -G firehpc ${USERNAME}
```

```
$ curl -s https://hpck.it/keyring.asc | \
  sudo gpg --no-default-keyring --keyring=/etc/systemd/import-pubring.gpg --import
```

```
gpg: key F2EB7900E8151A0D: public key "HPCk.it team <contact@hpck.it>" imported
gpg: Total number processed: 1
gpg:               imported: 1
```

https://github.com/systemd/systemd/issues/21397

On Debian 12, start and enable `systemd-networkd` service:

```
sudo systemctl start systemd-networkd.service
sudo systemctl enable systemd-networkd.service
```

Then, with your regular user, run FireHPC with a zone name and an OS in
arguments. For example:

```
$ firehpc deploy --zone hpc --os debian11
```

**NOTE:** Supported OS are _debian11_ and _rocky8_.

You can connect to your containers (eg. _admin_) with this command:

```
machinectl shell admin.hpc
```

Or using SSH with this command:

```
ssh -o UserKnownHostsFile=~/.local/state/firehpc/hpc/ssh/known_hosts -i ~/.local/state/firehpc/hpc/ssh/id_rsa root@admin.hpc
```

Connect with a test user account (_marie_ or _pierre_) on the login node:

```
ssh -o UserKnownHostsFile=~/.local/state/firehpc/hpc/ssh/known_hosts -i ~/.local/state/firehpc/hpc/ssh/id_rsa pierre@login.hpc
```

Then run MPI job in Slurm job:

```
[pierre@login ~]$ curl --silent https://raw.githubusercontent.com/mpitutorial/mpitutorial/gh-pages/tutorials/mpi-hello-world/code/mpi_hello_world.c -o helloworld.c
[pierre@login ~]$ export PATH=$PATH:/usr/lib64/openmpi/bin  # required on centos8, not on debian11
[pierre@login ~]$ mpicc -o helloworld helloworld.c
[pierre@login ~]$ salloc -N 2
salloc: Granted job allocation 2
[pierre@login ~]$ mpirun helloworld
Hello world from processor cn1.hpc, rank 0 out of 4 processors
Hello world from processor cn1.hpc, rank 1 out of 4 processors
Hello world from processor cn2.hpc, rank 2 out of 4 processors
Hello world from processor cn2.hpc, rank 3 out of 4 processors
```

When you are done, you can clean up everything for a zone with this command:

```
$ firehpc clean --zone hpc
```

## Authors

FireHPC is developed by [Rackslab](https://rackslab.io).

## License

FireHPC is distributed under the terms of the GNU General Public License v3.0 or
later (GPLv3+).
