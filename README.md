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

FireHPC requires Python >= 3.9.

FireHPC relies on:

- [`systemd-nspawn`](https://www.freedesktop.org/software/systemd/man/systemd-nspawn.html) containers controlled with `systemd-{networkd,machined}`
- [Ansible](https://docs.ansible.com/ansible/latest/index.html) automation tool

FireHPC also requires the following community Ansible collections:

- [community.general](https://docs.ansible.com/ansible/latest/collections/community/general/index.html) >= 3.8.1
- [community.crypto](https://docs.ansible.com/ansible/latest/collections/community/crypto/index.html)
- [community.mysql] (https://docs.ansible.com/ansible/latest/collections/community/mysql/index.html)

They may not be installed within Ansible on your distribution. In this case,
you can install on your system using `ansible-galaxy`.

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

Without this modification, the `mymachines` service is basically ignored by the
_return_ action on `resolve` service. For reference, see `nss-mymachines(8)`.

With your regular user, run FireHPC with a zone name and an OS in arguments. For
example:

```
$ firehpc deploy --zone hpc --os debian11
```

The available OS are reported by this command:

```
$ firehpc images
```

When it is deployed, check the status of the emulated cluster:

```
$ firehpc status --zone hpc
```

This reports the started containers and the randomly generated user accounts.

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

When you are done, you can clean up everything for a zone with this command:

```
$ firehpc clean --zone hpc
```

## Authors

FireHPC is developed by [Rackslab](https://rackslab.io).

## License

FireHPC is distributed under the terms of the GNU General Public License v3.0 or
later (GPLv3+).
