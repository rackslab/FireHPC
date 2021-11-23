#!/bin/sh

# Install polkit rules to authorize the `sudo` group to manage containers and
# images without prompting for password by deploying this polkit policy file.
echo "Installing polkit rules"
install -m644 etc/polkit/firehpc.pkla \
  /etc/polkit-1/localauthority/10-vendor.d/10-firehpc.pkla

# NOTE: There might be a bug with `systemd-machined` actions default polkit policy
# relying on `auth_admin_keep` permission, see TODO.md for details.
#
# NOTE: Unfortunately, Debian/Ubuntu do not distribute recent versions of polkit
# with support of Javascript rules files. The provided `*.pkla` file does not
# setup fine-grained permissions for FireHPC made possible with polkit Javascript
# rules. In particular, all members of the _sudo_ group have the permissions to
# manage all system units, this is not great.

# Install FireHPC container service template
echo "Installing container service template"
install -m644 etc/system/firehpc-container@.service \
  /etc/systemd/system/firehpc-container@.service

# Install `systemd-nspawn` wrapper
echo "Installing systemd-nspawn wrapper"
install -m755 lib/exec/firehpc-wrapper /usr/libexec/firehpc-wrapper
