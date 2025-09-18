# FireHPC: Instantly fire up container-based emulated HPC cluster

## Description

FireHPC is a tool designed to quickly deploy a tiny emulated HPC cluster based
on Linux containers, ready to run non-intensive MPI jobs with
[Slurm](https://slurm.schedmd.com/overview.html).

Obviously, FireHPC does not aim at performances as you get better performances
out of your computer without containers overhead.

The purposes are the following:

- Setup development, CI and tests environments
- Learn tools and software in breakable environment
- Testing and discovering new technologies in isolated environment

FireHPC aims to emulate HPC clusters with multiple distributions. It supports
running multiple emulated HPC clusters in parallel on the same host, each
cluster running in its dedicated virtual network.

The following services are automatically deployed in the emulated cluster:

- Slurm workload manager
- SlurmDBD accounting with MariaDB backend
- Slurmrestd REST API
- LDAP directory with TLS
- SSH with public keys
- OpenMPI

Additional components can be also be deployed, such as:

- [Slurm-web](https://slurm-web.com)
- Metrics stack with Prometheus, Grafana and Grafana Alloy

## Architecture

FireHPC requires Python >= 3.9.

FireHPC relies on:

- [RacksDB](https://github.com/rackslab/RacksDB) to get emulated clusters
  description.
- [`systemd-nspawn`](https://www.freedesktop.org/software/systemd/man/systemd-nspawn.html)
  containers controlled with `systemd-{networkd,machined}`
- [Ansible](https://docs.ansible.com/ansible/latest/index.html) automation tool

## Quickstart

Download and install Rackslab packages repository signing keyring:

```console
$ curl -sS https://pkgs.rackslab.io/keyring.asc | gpg --dearmor | sudo tee /usr/share/keyrings/rackslab.gpg > /dev/null
```

Create `/etc/apt/sources.list.d/rackslab.sources`:

* For Debian 12 _Bookworm_:

```
Types: deb
URIs: https://pkgs.rackslab.io/deb
Suites: bookworm
Components: main
Architectures: amd64
Signed-By: /usr/share/keyrings/rackslab.gpg
```

* For Debian 13 _Trixie_:

```
Types: deb
URIs: https://pkgs.rackslab.io/deb
Suites: trixie
Components: main
Architectures: amd64
Signed-By: /usr/share/keyrings/rackslab.gpg
```

* For Debian 14 _Forky_:

```
Types: deb
URIs: https://pkgs.rackslab.io/deb
Suites: forky
Components: main
Architectures: amd64
Signed-By: /usr/share/keyrings/rackslab.gpg
```

* For Debian _sid_:

```
Types: deb
URIs: https://pkgs.rackslab.io/deb
Suites: sid
Components: main
Architectures: amd64
Signed-By: /usr/share/keyrings/rackslab.gpg
```

Update packages database and install `firehpc`:

```console
$ sudo apt update && sudo apt install firehpc
```

Add your user in `firehpc` system group:

```console
$ sudo usermod -a -G firehpc ${USERNAME}
```

Import [hpck.it](https://hpck.it/) repository keyring to verify container images
signatures:

```console
$ curl -s https://hpck.it/keyring.asc | \
  sudo gpg --no-default-keyring --keyring=/etc/systemd/import-pubring.gpg --import
gpg: key F2EB7900E8151A0D: public key "HPCk.it team <contact@hpck.it>" imported
gpg: Total number processed: 1
gpg:               imported: 1
```

Enable and start `systemd-networkd` service:

```
$ sudo systemctl enable --now systemd-networkd.service
```

It is also recommended to increase maximum inotify instances from default 128 to
1024 for instance to avoid weird issues when starting a large number of
containers:

```console
# sysctl fs.inotify.max_user_instances=1024
```

Without this modification, the `mymachines` service is basically ignored by the
_return_ action on `resolve` service. For reference, see `nss-mymachines(8)`.

This can be made persistent with:

```console
# echo fs.inotify.max_user_instances=1024 > /etc/sysctl.d/99-firehpc.conf
```

## Usage

### Bootstrap

First, bootstrap deployment environments:

```console
$ firehpc bootstrap
```

> [!NOTE]
> This command creates multiple Python virtual environments with all versions of
> Ansible required for all supported target OS.

### Deploy

For a quick start, copy the simple example RacksDB database:

```console
$ cp /usr/share/doc/firehpc/examples/db/racksdb.yml racksdb.yml
```

This file can optionally be modified to add nodes or change hostnames.

With your regular user, run FireHPC with a cluster name and an OS in arguments.
For example:

```
$ firehpc deploy --db racksdb.yml --cluster hpc --os debian13
```

The available OS are reported by this command:

```
$ firehpc images
```

### Status

When it is deployed, check the status of the emulated cluster:

```
$ firehpc status --cluster hpc
```

This reports the started containers and the randomly generated user accounts.

### MPI

You can connect to cluster with this command:

```
$ firehpc ssh hpc
```

Connect with a generated user account on the login node:

```
$ firehpc ssh <user>@login.hpc
```

Then run MPI job in Slurm job:

```
[<user>@login ~]$ curl --silent https://raw.githubusercontent.com/mpitutorial/mpitutorial/gh-pages/tutorials/mpi-hello-world/code/mpi_hello_world.c -o helloworld.c
[<user>@login ~]$ export PATH=$PATH:/usr/lib64/openmpi/bin  # required on rocky8, not on debian11
[<user>@login ~]$ mpicc -o helloworld helloworld.c
[<user>@login ~]$ salloc -N 2
salloc: Granted job allocation 2
[<user>@login ~]$ mpirun helloworld
Hello world from processor cn1.hpc, rank 0 out of 4 processors
Hello world from processor cn1.hpc, rank 1 out of 4 processors
Hello world from processor cn2.hpc, rank 2 out of 4 processors
Hello world from processor cn2.hpc, rank 3 out of 4 processors
```

You can also try Slurm REST API:

```
[<user>@login ~]$ export $(scontrol token)
[<user>@login ~]$ curl -H "X-SLURM-USER-NAME: ${USER}" -H "X-SLURM-USER-TOKEN: ${SLURM_JWT}" http://admin:6820/slurm/v0.0.39/nodes
```

### Slurm-web

When Slurm-web is enabled, it is available at: http://admin.hpc/

### Metrics

When the metrics stack is enabled, Grafana is available at:
http://admin.hpc:3000/

Grafana is setup with a _Slurm_ dashboard showing diagrams of nodes states and
job queue by default.

### Clean

When you are done, you can clean up everything for a cluster with this command:

```
$ firehpc clean --cluster hpc
```

## Authors

FireHPC is developed by [Rackslab](https://rackslab.io).

## License

FireHPC is distributed under the terms of the GNU General Public License v3.0 or
later (GPLv3+).
