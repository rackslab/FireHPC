# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

### Changed
- Removed extra directory from source tree. It used to contain ansible
  machinectl connection plugin as Git submodule. This dependency is now injected
  in FireHPC as a package supplementary source in packages built by Fatbuildr.

## [1.0.0] - 2023-07-20

[unreleased]: https://github.com/rackslab/firehpc/compare/v1.0.0-beta...HEAD
[1.0.0]: https://github.com/rackslab/firehpc/releases/tag/v1.0.0-beta
