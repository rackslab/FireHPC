[defaults]
inventory = hosts
connection_plugins = ../../conf/connections/connection_plugins
interpreter_python = auto_silent
roles_path = ../../conf/roles

[ssh_connection]
ssh_args = -C -o ControlMaster=auto -o ControlPersist=60s -o UserKnownHostsFile=%LOCAL%/ssh/known_hosts -i %LOCAL%/ssh/id_rsa
