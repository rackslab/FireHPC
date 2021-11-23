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
- [ ] Run as non-root
  - [x] Define polkit config with permissions for password-less images/container management
  - [x] ~~Installation of *.spawn unit files with user permissions~~ → Not
       feasible as all directories looked by `systemd-nspawn` are restricted to
       administrator. The other identified option is to start a template unit
       with a wrapper over systemd-nspawn that looks for `systemd-nspawn`
       arguments in a temporary generated file.
  - [x] Develop template unit service file and wrapper
  - [x] Adapt FireHPC to launch the new specific service
  - [ ] Adapt Ansible machinectl connection plugin to allow execution an non-root
- [ ] Add some fake users
- [ ] Define tmpfiles.d for `systemd-nspawn` arguments (eg. bind-mounts)
- [ ] Fake shared filesystem
- [ ] Install Slurm controler, slurmd and clients
- [ ] Support RPM distribution
- [ ] Develop a real tool (ie. not a prototype) that can run anywhere

## Nice to have

- [ ] Manual install script to simplify quickstart
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
