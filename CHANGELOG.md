# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

### Added
- images:
  - Add rocky9
  - Add debian13
  - Add debian14 (#42).
- Introduce `fhpc_namespace` extra variable with the name of containers
  namespace.
- Add bash-completion script for `firehpc` command (#12).
- Add `firehpc list` command to list clusters present in state directory (#16).
- Add `firehpc restore` command to restore a cluster after restart or IP
  addresses change (#11→#31).
- Save cluster settings on deployment so they can reused automatically in
  subsequent runs of `firehpc conf` and `firehpc restore` (#7).
- Report cluster settings in `firehpc status`.
- Introduce `firehpc update` command to change cluster settings.
- Introduce `firehpc bootstrap` command to create deployment environments.
- Add `firehpc {conf,deploy} --ansible-opts` option to append additional options
  to `ansible-playbook` command (#44).
- Integrated management of virtual environment to multiple versions of Ansible
  depending on targeted OS (#24).
- Add PIP requirements files to populate _ansible-latest_ and _ansible-2.16_
  deployment environments.
- load:
  - Submit jobs randomly in existing QOS and partitions.
  - Submit jobs of various sizes, with a power of 2 number (1, 2, 4, 8…) of
    cores or nodes, up to the full size of the cluster. A number of nodes is
    selected when Slurm SelectType plugin is linear, a number of cores is
    selected otherwise. Small jobs are more submitted than big jobs.
  - Select job partition randomly weighted by their number of resources to favor
    largest partitions.
  - Make some (about 1/10th) submitted jobs randomly fail (#9).
  - Submit jobs with random durations and timelimit with low probability for
    jobs to reach their timelimit (#10).
  - Support Slurm configuration without accounting service and QOS.
  - Reduce load by a factor outside of business hours to simulate humans
    submitting less jobs when not at work (#29).
  - Add `--time-off-factor` option to control by how much the load is divided
    outside of business hours.
  - Request GPUs allocations on partitions with gpu GRES.
- conf:
  - Add possibility to define additional QOS and alternative partitions in
    Slurm.
  - Add support for RHEL9 and compatibles distributions.
  - Add possibility to define custom site file name in nginx role.
  - Introduce metrics role to deploy prometheus, alloy and grafana.
  - Declare nodes in Slurm configuration with their socket/cores/memory
    configuration extracted from RacksDB.
  - Add `params` key in `slurm_partitions` parameter to give possibility to
    set any arbitrary Slurm partition configuration parameter in inventory.
  - Support Slurm native authentication in alternative to munge (#22).
  - Add possibility to disable deployment of SlurmDBD accounting service (#20).
  - Enable SlurmDBD regular archive and purge mechanism to avoid MariaDB
    database growing too much (#28). This can be disabled with
    `slurm_with_db_archive: false` in custom configuration.
  - Add restore playbook to update hosts file, restart Slurm services and resume
    unavailable nodes.
  - Add _mariadb_ and _dependencies_ tags on _mariadb_ role in _slurm_ role
    dependencies.
  - Support possibility to change priorities of hpck.it and Rackslab development
    repositories derivatives with `common_hpckit_priorities` and
    `common_devs_priorities`.
  - Add `slurm_restd_port` variable in inventory to control slurmrestd TCP/IP
    listening port.
  - Support all Slurm-web to slurmrestd JWT authentication modes.
  - Support gpu GRES in Slurm configuration (#39).
- docs:
  - Add sysctl `fs.inotify.max_user_instances` value increase recommendation in
    README.md to avoid weird issue when launching many containers.
  - Mention Metrics stack and Slurm-web optional features in README.md with URL
    to access Grafana and Slurm-web interfaces.
  - Explain in README.md Ansible core 2.16 requirement for both _rocky8_ and
    _debian13_ clusters with a method to install this version from PyPI
    repository.
  - Mention `firehpc list` command in manpage.
  - Mention `firehpc load` command in manpage.
  - Mention `firehpc restore` command in manpage.
  - Mention `firehpc bootstrap` command in manpage.
  - Mention cluster settings and `firehpc update` command in manpage.
  - Update README.md to mention bootstrap step in usage guide.
  - Mention `--ansible-opts` option in manpage.
- pkgs: Introduce tests extra package with dependencies required to run tests.

### Changed
- Replace `fhpc-emulate-slurm-usage` command by `firehpc load` (#13).
- Transform `fhpc_nodes` dictionary values from list of nodes to list of
  dictionaries to group nodes by type in RacksDB.
- `firehpc ssh <cluster>` now connects to _admin_ host by default (#8).
- Rename file `images.yml` to `os/db.yml` and name of deployment environment
  associated to all supported OS.
- Replace section `[images]` to `[os]` in system configuration with new `db` and
  `requirements` parameters.
- load:
  - Change pending jobs limit formula to avoid number of jobs growing as fast as
    the number of nodes.
  - Consider running jobs in addition to pending jobs when computing the number
    of new jobs to submit, in order to significantly reduce load on clusters out
    of working hours.
- conf:
  - Install `socat` package on all nodes in _common_ role.
  - Use packages list instead of loop to install MariaDB packages.
  - Enable `config_overrides` slurmd parameter in Slurm configuration to avoid
    compute nodes sockets/cores/memory matching configuration check.
  - Move `maxtime` and `state` Slurm partitions parameters in `params`
    sub-dictionary.
  - Rename `slurm_partitions` > `node`→`nodes` key.
  - Change default Slurm authentication plugin from munge to slurm. This can be
    changed by setting `slurm_with_munge: true` in Ansible inventory.
  - Launch `slurmrestd` with unprivileged system user when JWT authentication is
    enabled.
  - Adapt _slurm_ role to support Slurm upstream packages on Debian.
- docs:
  - Explain in manpage ssh command considers admin container by default.
  - Update documentation of `--db`, `--schema`, `--custom` and
    `--slurm-emulator` options of `conf` and `restore` commands with their new
    semantics regarding management of cluster settings.

### Fixed
- core:
  - Properly handle DBus error when getting containers addresses.
  - Potential key conflict in dictionnary of SSH clients when multiple users
    connect to the same host with Paramiko library.
  - Set jobs time limit to partition time limit when set to avoid jobs that
    exceed partition time limit.
  - Remove cluster state on cluster clean.
  - Check ansible playbook RC code and stop execution on failure.
- lib: Fix `firehpc-storage-wrapper` start failure due to already existing
  cluster and home directories.
- load:
  - Order of partition/qos variables in job submission informational message.
  - Support of Slurm 24.05 `sacctmgr show qos --json` format to retrieve the
    list of defined QOS.
  - Redirect jobs output to `/dev/null` to avoid filling filesystems with tons
    of inodes (#27).
- conf:
  - Install mpi packages in parallel instead of sequential loop.
  - Configure system locale to `en_US.UTF-8` on rocky8.
  - Add SLURMRESTD_SECURITY=disable_user_check environment variable in
    slurmrestd service to allow running as slurm user.
  - Containers namespace missing in Slurm-web gateway `[ui]` > `host`.
  - Force creation of CA and LDAP certificates to override possibly existing
    certificates during bootstrap.
  - Ignore cluster creation error in slurmdbd, as it is now automatically
    created when slurmctld registers to accounting service.
  - Support Rackslab development repository derivatives on RHEL.
  - Add admin hostname with namespace in addition to just the admin hostname in
    Slurm-web nginx site server names.
- docs: Various formatting errors in manpage.

### Removed
- conf: Drop DSA SSH host keys.
- docs: Remove `fhpc-emulate-slurm-usage` manpage.

## [1.1.0] - 2024-05-07

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
- Support containers namespace to allow multiple users start the same virtual
  clusters on the same host without conflict.
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
  - Install `bach-completion` by default on all nodes with _common_ role.
  - Install `clustershell` on all nodes by default with new _clustershell_
    role (#3).
  - Introduce _nginx_ role.
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
- Correctly handle and report DNS errors in SSH module.
- conf:
  - Open slurmd spool directory permissions to all users for running batch
    jobs scripts.
  - Manage home directories ownership and permissions, in addition to some their
    content.
  - Add missing common name in LDAP x509 TLS/SSL certificate.
  - Do not use cgroups with Slurm in emulator mode.
  - Force update of APT repositories metadata.
  - Install `en_US.UTF-8` locale on Debian, as well as done on RHEL by default.
  - Set `systemd-networkd` DHCP client identifier to mac on RHEL to avoid
    getting a different address than those obtained by NetworkManager at boot,
    which eventually result in IPv4 adresses in `/etc/hosts` being removed from
    network interfaces when initial leases reach their timeout.
- docs: Grammatical error and typos in `firehpc(1)` manpage
- lib: limit network devices names to 12 characters to avoid network zone name
  errors with `systemd-nspawn`.

## [1.0.0] - 2023-07-20

[unreleased]: https://github.com/rackslab/firehpc/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/rackslab/firehpc/releases/tag/v1.1.0
[1.0.0]: https://github.com/rackslab/firehpc/releases/tag/v1.0.0
