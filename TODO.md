# TODO

## Must have

- [x] Generate SSH host keys with ansible
- [x] Generate SSH known hosts\_file for local client
- [x] Install OpenSSH with SSH host keys
- [ ] Generate root SSH keys
- [ ] List of key types as variable
- [ ] Deploy root authorized\_keys
- [ ] Develop a common role
- [x] Generate SSH keys and known\_hosts in ssh role
- [ ] Run as non-root

## Nice to have

- [ ] Build and deploy mkosi images with python3 pre-installed
- [ ] Fix shell glitch after ansible run with machinectl connection
- [ ] Understand why the hostname is not set automatically in containers (I though systemd-hostnamed would do the job)
