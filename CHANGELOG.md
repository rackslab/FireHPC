# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]
### Added
- Support for debian12 (Debian bookworm) in OS images sources YAML file.
- Introduce fhpc_addresses extra variable, a hash with containers as keys and
  the list of IP addresses as values.
- Possibility to run command with SSH paramiko library in addition to ssh binary
  executable.
- cli:
  - Support for tags to filter deployed configuration tasks.
  - Report cluster status in JSON format with --json option.
  - Introduce fhpc-emulate-slurmu command to emulate random usage of Slurm
    cluster.
- conf:
  - Optional support of Rackslab developement deb repositories, disabled by
    default.
  - slurmweb role to install and setup Slurmweb, optional and disabled by
    default.
  - Support multiple Slurm accounts definitions with hierarchy and control of
    users membership.
  - Add tags on all roles.
  - Add variable for slurmrestd socket path in slurm role.
  - Support optional additional slurmdbd parameters.
  - Deploy SSH root private and public keys on admin.
  - Generate /etc/hosts with all zone IP addresses and hostnames.
- docs:
  - Mention conf --tags option in manpage.
  - Mention status --json option in manpage.

### Changed
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

### Fixed
- Check OS images argument in CLI against values available in OS images YAML
  file instead of hard-coded argparse choices.
- conf: Open slurmd spool directory permissions to all users for running batch
  jobs scripts.

## [1.0.0] - 2023-07-20

[unreleased]: https://github.com/rackslab/firehpc/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/rackslab/firehpc/releases/tag/v1.0.0
