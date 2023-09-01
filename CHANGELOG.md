# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]
### Added
- Support for debian12 (Debian bookworm) in OS images sources YAML file.
- cli: Support for tags to filter deployed configuration tasks.
- conf:
  - Optional support of Rackslab developement deb repositories, disabled by
    default.
  - slurmweb role to install and setup Slurmweb, optional and disabled by
    default.
  - Support multiple Slurm accounts definitions with hierarchy and control of
    users membership.
  - Add tags on all roles.
  - Add variable for slurmrestd socket path in slurm role.
- docs: Mention conf --tags option in manpage.

### Changed
- Removed extra directory from source tree. It used to contain ansible
  machinectl connection plugin as Git submodule. This dependency is now injected
  in FireHPC as a package supplementary source in packages built by Fatbuildr.

### Fixed
- Check OS images argument in CLI against values available in OS images YAML
  file instead of hard-coded argparse choices.

## [1.0.0] - 2023-07-20

[unreleased]: https://github.com/rackslab/firehpc/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/rackslab/firehpc/releases/tag/v1.0.0
