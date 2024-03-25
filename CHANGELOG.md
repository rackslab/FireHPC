# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]
### Added
- Integration with [RacksDB](https://github.com/rackslab/RacksDB) to extract
  emulated cluster topology (#1).
- Support for debian12 (Debian bookworm) in OS images sources YAML file.
- Introduce `fhpc_addresses`, `fhpc_nodes`, `fhpc_emulator_mode` and `fhpc_db`
  extra variables. The first is a hash with containers as keys and the list of
  IP addresses as values. The second is also a hash with node tags as keys and
  the list of nodes assigned with the tag in values. The third is a boolean set
  to true when `--slurm-emulator` option is set on `firehpc` command line. The
  fourth is the local absolute path to RacksDB database.
- Possibility to run command with SSH paramiko library in addition to ssh binary
  executable.
- Add example RacksDB database.
- Add possibility to deploy users directory extracted from another existing
  cluster to have the same user accounts on multiple clusters eventually.
- Generate and manage groups tree internally. Groups definitions are exported to
  ansible with `fhpc_groups` extra variable and can be dumped with
  `firehpc status` command.
- cli:
  - Support for tags to filter deployed configuration tasks.
  - Report cluster status in JSON format with `--json` option.
  - Add `--slurm-emulator` option to deploy and configure a cluster with
    emulated Slurm cluster nodes (only one admin node with up to 64k virtual
    compute nodes).
  - Add `--users` option on deploy command to extract users directory from
    another existing cluster.
  - Introduce `fhpc-emulate-slurm-usage` command to emulate random usage of
    Slurm cluster.
  - Add `start` and `stop` commands to respectively start and stop all
    containers of an emulated cluster.
- conf:
  - Optional support of Rackslab developement Deb and RPM repositories, disabled
    by default.
  - Introduce _racksdb_ role to install RacksDB and deploy database content.
  - Introduce _slurmweb_ role to install and setup Slurmweb, optional and
    disabled by default.
  - Support multiple Slurm accounts definitions with hierarchy and control of
    users membership.
  - Add tags on all roles.
  - Add variable for slurmrestd socket path in slurm role.
  - Support optional additional slurmdbd parameters.
  - Deploy SSH root private and public keys on admin.
  - Generate /etc/hosts with all cluster IP addresses and hostnames.
  - Add `nodeset_fold` and `nodeset_expand` Jinja2 filters.
  - Support Slurm emulation with fully virtual nodes (up to 64k).
  - Support optional secondary groups in LDAP directory.
  - Add possibility to deploy Redis server on admin host.
  - Use `fhpc_groups` for default `slurm_accounts` variable value and to define
    LDAP groups.
  - Use `fhpc_db` for default `racksdb_database` variable value and to define
    RacksDB database content.
- docs:
  - Mention `conf` command `--db`, `--schema` and `--tags` options in
    `firehpc(1)` manpage.
  - Mention `deploy` command `--db` and `--schema` options in `firehpc(1)`
    manpage.
  - Mention `status` command `--json` option in `firehpc(1)` manpage.
  - Mention new `start` and `stop` commands in `firehpc(1)` manpage.
  - Add manpage for `fhpc-emulate-slurm-usage`
  - Mention `conf` and `deploy` commands `--slurm-emulator` option in
    `firehpc(1)` manpage.
  - Mention `deploy` command `--users` option in `firehpc(1)` manpage.

### Changed
- Replaced notion of zone in favor of cluster, both in CLI options and
  configuration variables names.
- Removed extra directory from source tree. It used to contain ansible
  machinectl connection plugin as Git submodule. This dependency is now injected
  in FireHPC as a package supplementary source in packages built by Fatbuildr.
- conf:
  - Declare SSH host keys valid for both containers FQDN and short hostname
    in system known hosts file.
  - Split ssh role in 3 steps: localkeys for local bootstrap, bootstrap to
    initialize files on containers with machinectl and main for normal
    operations with SSH (known_hosts, SSH root keys).
  - Replace hardcoded admin hosts by selection of first admin group member for
    LDAP server hostname and Slurm server.
  - Generate Slurm nodes and partitions based RacksDB database content.
  - Split playbook by sections with hosts targets to avoid many skipped tasks.
- docs: Update after zone→cluster rename in CLI options.

### Fixed
- Check OS images argument in CLI against values available in OS images YAML
  file instead of hard-coded argparse choices.
- Storage service stop and removal.
- Start storage service with container when cluster is started.
- Retry SSH connections up to 3 times in case of failure.
- Wait some time before starting the second container to finish container
  private network setup and avoid the following container from erasing
  everything before completion.
- Handle RacksDB format and schema errors with correct error message.
- Wait for both IPv4 and IPv6 addresses when retrieving container addresses, to
  avoid retrieving only IPv6 before IPv4 address is finally available.
- conf:
  - Open slurmd spool directory permissions to all users for running batch
    jobs scripts.
  - Manage home directories ownership and permissions, in addition to some their
    content.
  - Add missing common name in LDAP x509 TLS/SSL certificate.
  - Do not use cgroups with Slurm in emulator mode.
  - Force update of APT repositories metadata.
  - Install `en_US.UTF-8` locale on Debian, as well as done on RHEL by default.
- docs: Grammatical error and typos in `firehpc(1)` manpage

## [1.0.0] - 2023-07-20

[unreleased]: https://github.com/rackslab/firehpc/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/rackslab/firehpc/releases/tag/v1.0.0
