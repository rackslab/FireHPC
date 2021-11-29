# TODO

## Must have

- [x] Generate SSH host keys with ansible
- [x] Generate SSH known hosts\_file for local client
- [x] Install OpenSSH with SSH host keys
- [x] Generate root SSH keys
- [x] List of key types as variable
- [x] Deploy root authorized\_keys
- [x] Develop a common role
- [x] Generate SSH keys and known\_hosts in ssh role
- [x] Run as non-root
  - [x] Define polkit config with permissions for password-less images/container management
  - [x] ~~Installation of *.spawn unit files with user permissions~~ → Not
       feasible as all directories looked by `systemd-nspawn` are restricted to
       administrator. The other identified option is to start a template unit
       with a wrapper over systemd-nspawn that looks for `systemd-nspawn`
       arguments in a temporary generated file.
  - [x] Develop template unit service file and wrapper
  - [x] Adapt FireHPC to launch the new specific service
  - [x] Adapt Ansible machinectl connection plugin to allow execution an non-root
- [x] Add some fake users
- [x] Fake shared /home filesystem
- [x] Use SSH for ansible once it is setup
- [x] Install Slurm controler, slurmd and clients
- [x] SSH key pair and authorized_keys for users
- [x] Deploy system known_host on all nodes
- [x] Add users in SlurmDBD accounting
- [x] Bootstrap MariaDB password in local file
- [x] Install OpenMPI
- [x] Introduce groups and inventory 
- [ ] Fully support zones and parallel FireHPC clusters
- [ ] Support RPM distribution
- [ ] Define tmpfiles.d for `systemd-nspawn` arguments (eg. bind-mounts)
- [ ] Develop a real tool (ie. not a prototype) that can run anywhere
- [ ] RELEASE THE SHMOO!

## Nice to have

- [x] Rename front to login as this name in more common in HPC
- [ ] Generate slurm partitions and nodes conf based on inventory → This would
      requires a new filter, roughly similar to ansible.netcommon.vlan_parser,
      to generate nodesets based on host lists.
- [ ] Use triggered unit to manage (create/remove) shared directories
- [ ] Improve rackslab/ansible-connection-machinectl _non-root_ branch to match
      [maintainer expectations](https://github.com/tomeon/ansible-connection-machinectl/issues/10#issuecomment-812534935).
- [x] Manual install script to simplify quickstart
- [ ] Build and deploy mkosi images with python3 pre-installed
- [ ] Fix shell glitch after ansible run with machinectl connection
- [ ] Understand why the hostname is not set automatically in containers (I
      though `systemd-hostnamed` would do the job)
- [ ] Understand why polkit `auth_admin_keep` permission for active sessions on
      `org.freedesktop.machine1.*` actions are not effective (at least on
      Ubuntu 21.10). An additional rule is required to avoid typing password
      for all `machinectl` commands:

  ```
  $ pkaction --action-id org.freedesktop.machine1.shell --verbose
  org.freedesktop.machine1.shell:
    description:       Acquire a shell in a local container
    message:           Authentication is required to acquire a shell in a local container.
    vendor:            The systemd Project
    vendor_url:        http://www.freedesktop.org/wiki/Software/systemd
    icon:
    implicit any:      auth_admin
    implicit inactive: auth_admin
    implicit active:   auth_admin_keep
    annotation:        org.freedesktop.policykit.imply -> org.freedesktop.login1.login

  $ machinectl shell cn2
  Connected to machine cn2. Press ^] three times within 1s to exit session.
  root@cn2:~# exit
  logout
  Connection to machine cn2 terminated.

  $ pkcheck --list-temp
  <nothing>
  ```
     → Try on Fedora workstation to check if things are better.
