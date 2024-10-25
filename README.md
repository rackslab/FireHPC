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

- [`systemd-nspawn`](https://www.freedesktop.org/software/systemd/man/systemd-nspawn.html) containers controlled with `systemd-{networkd,machined}`
- [Ansible](https://docs.ansible.com/ansible/latest/index.html) automation tool

FireHPC also requires the following community Ansible collections:

- [community.general](https://docs.ansible.com/ansible/latest/collections/community/general/index.html) >= 3.8.1
- [community.crypto](https://docs.ansible.com/ansible/latest/collections/community/crypto/index.html)
- [community.mysql](https://docs.ansible.com/ansible/latest/collections/community/mysql/index.html)

They may not be installed within Ansible on your distribution. In this case,
you can install on your system using `ansible-galaxy`.

## Quickstart

Download and install Rackslab packages repository signing keyring:

```
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

* For Debian _sid_:

```
Types: deb
URIs: https://pkgs.rackslab.io/deb
Suites: sid
Components: main
Architectures: amd64
Signed-By: /usr/share/keyrings/rackslab.gpg
```

Update packages database:

```
$ sudo apt update
```

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

Start and enable `systemd-networkd` service:

```
$ sudo systemctl start systemd-networkd.service
$ sudo systemctl enable systemd-networkd.service
```

Install `systemd-resolved`:

```
$ sudo apt install systemd-resolved
```

Unfortunarly, there is on ongoing [bug #1031236 in Debian](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1031236)
on `ifupdown`/`systemd-resolved` automatic integration. One workaround is to
define DNS servers IP addresses and domains in `systemd-resolved` configuration
file `/etc/systemd/resolved.conf`. Then restart the service so changes can take
effect:

```
$ sudo systemctl restart systemd-resolved.service
```

Fix the order between `mymachine` and `resolve` services in `/etc/nsswitch.conf`
so the `mymachines` service can resolve IP addresses of container names:

```diff
--- a/etc/nsswitch.conf
+++ b/etc/nsswitch.conf
@@ -9,7 +9,7 @@
 shadow:         files systemd sss
 gshadow:        files systemd
 
-hosts:          files resolve [!UNAVAIL=return] dns mymachines myhostname
+hosts:          files mymachines resolve [!UNAVAIL=return] dns myhostname
 networks:       files
 
 protocols:      db files
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

Deployment of Debian 13 _« trixie »_ clusters require Ansible core >= 2.16 (for
[this fix](https://github.com/ansible/ansible/issues/82068)) while RHEL8 target
is not supported by Ansible >= 2.17 because of dropped support of Python 3.6
(see
[ansible support matrix](https://docs.ansible.com/ansible-core/devel/reference_appendices/release_and_maintenance.html#ansible-core-support-matrix)
for reference). This means Ansible core 2.16 is the only compatible release if
you want to deploy both RHEL8 and Debian 13 _« trixie »_ clusters. The easiest
way to satisfy this requirement is to install Ansible from PyPI repository.
Create a virtual environment and install ansible with this command:

```console
$ pip install 'ansible-core<2.17' ansible ansible-runner ClusterShell
```

> [!NOTE]
> ClusterShell is required in the virtual environment for the
> [NodeSet filters](lib/ansible/filters/NodesetFilter.py).

## Usage

### Deploy

For a quick start, copy the simple example RacksDB database:

```console
$ cp /usr/share/doc/firehpc/examples/db/racksdb.yml racksdb.yml
```

This file can optionally be modified to add nodes or change hostnames.

With your regular user, run FireHPC with a cluster name and an OS in arguments.
For example:

```
$ firehpc deploy --db racksdb.yml --cluster hpc --os debian12
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

You can connect to your containers (eg. _admin_) with this command:

```
$ firehpc ssh admin.hpc
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
