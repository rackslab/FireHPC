# Vendored in FireHPC from ansible-connection-machinectl, commit
# 6bba4355693b4bfd0426f01753d53922aae52c21:
# https://github.com/tomeon/ansible-connection-machinectl
#
# FireHPC modifications: support non-root users, find machine user with
# getent in the right machine, set TERM=dumb for machinectl, find machinectl
# with shutil.which and explain why copy-to cannot overwrite files.
#
# Merged with upstream branch master, commit
# 9356fcf8db92be9702b08c733482b38456ec174c.
#
# Inspired by, but since deviated entirely from, the nsenter connection plugin
# (c) 2015, Tomohiro NAKAMURA <quickness.net@gmail.com>
# Permalink: https://github.com/jptomo/ansible-connection-nsenter/blob/4ab713b061c92eaf2553a5c826cd26266e932b09/nsenter.py
#
# The polling loop in Connection.exec_command was adapted from local.py
# (c) 2012, Michael DeHaan <michael.dehaan@gmail.com>
# (c) 2015 Toshio Kuratomi <tkuratomi@ansible.com>
# Permalink: https://github.com/ansible/ansible/blob/a9d5bf717c200126c46433de1a833f2dd34397f6/lib/ansible/plugins/connection/ssh.py#L332-L340
#
# The pty.getpty() code in Connection.exec_command was adapated from ssh.py
# (c) 2012, Michael DeHaan <michael.dehaan@gmail.com>
# Copyright 2015 Abhijit Menon-Sen <ams@2ndQuadrant.com>
# Permalink: https://github.com/ansible/ansible/blob/a9d5bf717c200126c46433de1a833f2dd34397f6/lib/ansible/plugins/connection/ssh.py#L332-L340
#
# Connection plugin for machinectl virtual machines and containers
# (c) 2016, Matt Schreiber <schreibah@gmail.com>
#
# This machinectl connection plugin is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import collections
import fcntl
import os
import pty
import re
import select
import shlex
import subprocess

try:
    from shutil import which as find_executable
except ImportError:  # Python 2
    from distutils.spawn import find_executable

from ansible.errors import AnsibleError, AnsibleFileNotFound
from ansible.plugins.connection import ConnectionBase
from ansible.utils.vars import merge_hash

try:
    from ansible.module_utils.common.text.converters import to_bytes, to_native
except ImportError:
    try:
        from ansible.module_utils._text import to_bytes, to_native
    except ImportError:
        from ansible.utils.unicode import to_bytes
        from ansible.utils.unicode import to_str as to_native

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class MachineCtl(object):

    # Suppress some diagnostic info that is not relevant when running
    # non-interactively.  This is one notch below the default 'info' level; see
    # `man 1 systemd'.
    SYSTEMD_LOG_LEVEL = 'notice'

    # Prior to version 230, `machinectl' consumed all flags in the `shell'
    # invocation, including those intended for the executed command.  See:
    # https://github.com/systemd/systemd/issues/2420
    MACHINECTL_GETOPT_FIX_VERSION = '230'

    # Tell the machine that `shell' commands run on a dumb terminal, as newer
    # versions of machinectl do by themselves when their output is not a
    # terminal.  Otherwise systemd 258 and later inside the machine write OSC
    # 3008 context sequences (https://systemd.io/OSC_CONTEXT) into the
    # command's output, which older versions of machinectl pass through.
    SHELL_OPTS = ['--setenv=TERM=dumb']

    def __init__(self, command=None):
        if command is not None:
            self.command = command
        else:
            self.command = find_executable('machinectl')
            if not self.command:
                raise AnsibleError('machinectl executable not found in PATH')

        self.version = self._version()

    @classmethod
    def machinectl_env(cls, **kwargs):
        '''
        Copy the current environment, merging keyword arguments and setting
        the systemd log level.
        '''
        # Add TERM=dump to disable OSC control sequences which mess commands
        # standard output captures.
        return dict(merge_hash(os.environ, kwargs),
                    SYSTEMD_LOG_LEVEL=cls.SYSTEMD_LOG_LEVEL,
                    TERM='dumb')

    def _version(self):
        ''' Queries the installed version of machinectl/systemd '''

        try:
            version_output = subprocess.check_output([self.command, '--version'])
            matched = re.match(r'\Asystemd\s+(\d+)\D', to_native(version_output))
            return (matched.groups())[0]
        except subprocess.CalledProcessError as e:
            raise AnsibleError('failed to retrieve machinectl version: {0}'.format(e))

    def property(self, wanted, machine=None):
        ''' Returns the value of a single machine property '''
        for prop, value in self.show(machine, '--property={0}'.format(wanted)):
            if wanted == prop:
                return value

    def build_command(self, action, opts=[], args=[], machine=None):
        '''
        Constructs a machinectl command with proper argument ordering.
        Special-cases arguments to the shell subcommand if appropriate.
        '''

        if action == 'shell':
            opts = self.SHELL_OPTS + opts

        local_cmd = [self.command] + opts + [action]

        if machine is not None:
            local_cmd.append(machine)

        if action == 'shell' and self.version < self.MACHINECTL_GETOPT_FIX_VERSION:
            local_cmd.append('--')

        return local_cmd + args

    def popen_command(self, action, opts=[], args=[], machine=None, **kwargs):
        '''
        Opens a command targeting the the specified machine

        :arg action: byte string containing the machinectl subcommand
        :kwarg opts: a list of byte strings representing flags to machinectl
        :kwarg args: a list of byte string representing parameters specific to
          ``action``
        :kwarg machine: a byte string representing a machine name
        :kwarg stdin: standard input of the opened process
        :type stdin: :data:`subprocess.PIPE`, file descriptor, or None
        :kwarg stdout: standard output of the opened process
        :type stdin: :data:`subprocess.PIPE`, file descriptor, or None
        :kwarg stderr: standard error of the opened process
        :type stdin: :data:`subprocess.PIPE`, :data:`subprocess.STDOUT`, file descriptor, or None
        :returns: an open process
        :rtype: :class:`subprocess.Popen`
        '''

        machinectl_env = self.machinectl_env()
        local_cmd = self.build_command(action, opts=opts, args=args, machine=machine)

        display.vvv(u'EXEC {0}'.format(local_cmd,), host=(machine or 'NONE'))

        local_cmd = [to_bytes(i, errors='strict') for i in local_cmd]

        stdin = kwargs.get('stdin', None)
        stdout = kwargs.get('stdout', subprocess.PIPE)
        stderr = kwargs.get('stderr', subprocess.PIPE)

        # TODO why can't we set stdin to a pipe?
        return subprocess.Popen(local_cmd, env=machinectl_env, shell=False,
                                stdin=stdin, stdout=stdout, stderr=stderr)

    def run_command(self, action, opts=[], args=[], machine=None, in_data=None):
        '''
        Wrapper for :func:`popen_command` that handles passing input data to
        the opened process.

        Unlike :func:`popen_command`, does not accept arguments for standard
        input, standard output, or standard error, but does recognize the
        additional argument ``in_data``.

        :kwarg in_data:
        '''

        p = self.popen_command(action, opts=opts, args=args, machine=machine)
        stdout, stderr = p.communicate(in_data)
        return (p.returncode, stdout, stderr)

    def list(self):
        ''' Returns a list of machine names '''
        returncode, stdout, stderr = self.run_command('list', opts=['--no-legend'])

        for i in to_native(stdout.strip()).splitlines():
            yield re.split(r'\s+', i)

    def show(self, machine=None, *args):
        ''' Yields machine properties in key-value pairs '''
        returncode, stdout, stderr = self.run_command('show', machine=machine)

        for line in to_native(stdout).splitlines():
            yield line.strip().split('=', 2)


class Connection(ConnectionBase):
    ''' Local connection based on systemd's machinectl '''

    transport = 'machinectl'

    # machinectl's shell subcommand expects to be connected to a terminal;
    # otherwise, it ignore standard input.  This means that we can't use
    # pipelining -- quoting the SSH connection plugin:
    #
    #   we can only use tty when we are not pipelining the modules. piping
    #   data into /usr/bin/python inside a tty automatically invokes the
    #   python interactive-mode but the modules are not compatible with the
    #   interactive-mode ("unexpected indent" mainly because of empty lines)
    has_pipelining = False

    def __init__(self, play_context, new_stdin, *args, **kwargs):
        super(Connection, self).__init__(play_context, new_stdin, *args, **kwargs)

        self.machinectl = MachineCtl(kwargs.get('machinectl_command'))
        self.remote_uid = None
        self.remote_gid = None
        self._flags = collections.defaultdict(lambda: False)

    def _parse_passwd(self, entry):
        if entry is None:
            return entry
        return entry.split(':')

    def _remote_passwd(self, user, passwd_path=None):
        if user is None:
            user = self._play_context.remote_user

        if user is None:
            return

        for getent in ['/bin/getent', '/usr/bin/getent']:
            try:
                returncode, stdout, stderr = self._run_command('shell', args=[getent, 'passwd', user], machine=self.machine)
            except AnsibleError:
                pass

            if returncode == 0:
                return self._parse_passwd(stdout.decode())

        try:
            if passwd_path is None:
                passwd_path = os.path.join(self.chroot, 'etc/passwd')

            with open(passwd_path, 'r') as passwdf:
                for entry in passwdf.readlines():
                    parsed = self._parse_passwd(entry)
                    if parsed[0] == self._play_context.remote_user:
                        return parsed
        except IOError:
            return

    def _connect(self):
        ''' Connection ain't real '''
        super(Connection, self)._connect()

        if not self._connected:
            self.machine = self._play_context.remote_addr

            display.vvv(u'ESTABLISH MACHINECTL CONNECTION FOR USER: {0}'.format(
                self._play_context.remote_user or '?'), host=self.machine
            )

            if self.machinectl.property('State', self.machine) != 'running':
                raise AnsibleError('machine {0} is not running'.format(self.machine))

            self.chroot = self.machinectl.property('RootDirectory', self.machine)

            display.vvv(u'MACHINE RUNNING FROM HOST DIRECTORY {0}'.format(self.chroot), host=self.machine)

            if self._play_context.remote_user is not None:
                self.chown_files = True

                remote_passwd = self._remote_passwd(self._play_context.remote_user)
                if remote_passwd is not None:
                    self.remote_uid = int(remote_passwd[2])
                    self.remote_gid = int(remote_passwd[3] or -1)
                else:
                    raise AnsibleError('failed to find UID or GID for {0}'.format(self._play_context.remote_user))
            else:
                self.chown_files = False

            self._connected = True

    def close(self):
        ''' Again, connection ain't real '''
        super(Connection, self).close()
        self._connected = False

    def _prefix_login_path(self, remote_path):
        ''' Make sure that we put files into a standard path

            If a path is relative, then we need to choose where to put it.
            ssh chooses $HOME but we aren't guaranteed that a home dir will
            exist in any given chroot.  So for now we're choosing "/" instead.
            This also happens to be the former default.

            Can revisit using $HOME instead if it's a problem
        '''
        if not remote_path.startswith(os.path.sep):
            remote_path = os.path.join(os.path.sep, remote_path)

        return os.path.normpath(remote_path)

    def _run_command(self, action, opts=[], args=[], machine=None, in_data=None):
        p = self.machinectl.popen_command(action, opts=opts, args=args, machine=machine)

        stdout, stderr = p.communicate(in_data)

        return (p.returncode, stdout, stderr)

    def _examine_output(self, source, state, chunk, sudoable):
        '''
        Takes a string, extracts complete lines from it, tests to see if they
        are a prompt, error message, etc., and sets appropriate flags in self.
        Prompt and success lines are removed.

        Returns the processed (i.e. possibly-edited) output and the unprocessed
        remainder (to be processed with the next chunk) as strings.
        '''

        def diag_state(header, source, state, line):
            display.debug("{0}: (source={1}, state={2}): '{3}'".format(header, source, state, line.rstrip('\n')))

        output = []
        for l in chunk.splitlines(True):
            suppress_output = False

            if self._play_context.prompt and self.check_password_prompt(l):
                diag_state('become_prompt', source, state, l)
                self._flags['become_prompt'] = True
                suppress_output = True
            elif self._play_context.success_key and self.check_become_success(l):
                diag_state('become_success', source, state, l)
                self._flags['become_success'] = True
                suppress_output = True
            elif sudoable and self.check_incorrect_password(l):
                diag_state('become_error', source, state, l)
                self._flags['become_error'] = True
            elif sudoable and self.check_missing_password(l):
                diag_state('become_nopasswd_error', source, state, l)
                self._flags['become_nopasswd_error'] = True

            if not suppress_output:
                output.append(l)

        # The chunk we read was most likely a series of complete lines, but just
        # in case the last line was incomplete (and not a prompt, which we would
        # have removed from the output), we retain it to be processed with the
        # next chunk.

        remainder = ''
        if output and not output[-1].endswith('\n'):
            remainder = output[-1]
            output = output[:-1]

        return ''.join(output), remainder

    # Used by _run() to kill processes on failures
    @staticmethod
    def _terminate_process(p):
        """ Terminate a process, ignoring errors """
        try:
            p.terminate()
        except (OSError, IOError):
            pass

    def exec_command(self, cmd, in_data=None, sudoable=False):
        super(Connection, self).exec_command(cmd, in_data=in_data, sudoable=sudoable)

        if in_data is not None:
            raise AnsibleError('the machinectl connection cannot perform pipelining')

        opts = []
        # --uid only recognized with `shell' subcommand
        if self.remote_uid is not None:
            display.vvv(u'RUN AS {0} (UID {1})'.format(self._play_context.remote_user, self.remote_uid))
            opts = ['--uid={0}'.format(self.remote_uid)]

        master, slave = pty.openpty()
        p = self.machinectl.popen_command('shell', opts=opts, args=shlex.split(cmd),
                                          machine=self.machine, stdin=slave)

        os.close(slave)
        stdin = os.fdopen(master, 'wb', 0)

        ## SSH state machine
        #
        # Now we read and accumulate output from the running process until it
        # exits. Depending on the circumstances, we may also need to write an
        # escalation password and/or pipelined input to the process.

        states = [
            'awaiting_prompt', 'awaiting_escalation', 'ready_to_send', 'awaiting_exit'
        ]

        # Are we requesting privilege escalation? Right now, we may be invoked
        # to execute sftp/scp with sudoable=True, but we can request escalation
        # only when using ssh. Otherwise we can send initial data straightaway.

        state = states.index('ready_to_send')
        if self._play_context.prompt:
            # We're requesting escalation with a password, so we have to
            # wait for a password prompt.
            state = states.index('awaiting_prompt')
            display.debug('Initial state: %s: %s' % (states[state], self._play_context.prompt))
        elif self._play_context.become and self._play_context.success_key:
            # We're requesting escalation without a password, so we have to
            # detect success/failure before sending any initial data.
            state = states.index('awaiting_escalation')
            display.debug('Initial state: %s: %s' % (states[state], self._play_context.success_key))

        # We store accumulated stdout and stderr output from the process here,
        # but strip any privilege escalation prompt/confirmation lines first.
        # Output is accumulated into tmp_*, complete lines are extracted into
        # an array, then checked and removed or copied to stdout or stderr. We
        # set any flags based on examining the output in self._flags.

        stdout = stderr = ''
        tmp_stdout = tmp_stderr = ''

        self._flags = dict(
            become_prompt=False, become_success=False,
            become_error=False, become_nopasswd_error=False
        )

        # select timeout should be longer than the connect timeout, otherwise
        # they will race each other when we can't connect, and the connect
        # timeout usually fails
        timeout = 2 + self._play_context.timeout
        rpipes = [p.stdout, p.stderr]
        for fd in rpipes:
            fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)

        # If we can send initial data without waiting for anything, we do so
        # before we call select.

        if states[state] == 'ready_to_send' and in_data:
            # TODO
            #self._send_initial_data(stdin, in_data)
            state += 1

        while True:
            rfd, wfd, efd = select.select(rpipes, [], [], timeout)

            # We pay attention to timeouts only while negotiating a prompt.

            if not rfd:
                if state <= states.index('awaiting_escalation'):
                    # If the process has already exited, then it's not really a
                    # timeout; we'll let the normal error handling deal with it.
                    if p.poll() is not None:
                        break
                    self._terminate_process(p)
                    raise AnsibleError('Timeout (%ds) waiting for privilege escalation prompt: %s' % (timeout, stdout))

            # Read whatever output is available on stdout and stderr, and stop
            # listening to the pipe if it's been closed.

            if p.stdout in rfd:
                chunk = to_native(p.stdout.read())
                if chunk == '':
                    rpipes.remove(p.stdout)
                tmp_stdout += chunk
                display.debug("stdout chunk (state=%s):\n>>>%s<<<\n" % (state, chunk))

            if p.stderr in rfd:
                chunk = to_native(p.stderr.read())
                if chunk == '':
                    rpipes.remove(p.stderr)
                tmp_stderr += chunk
                display.debug("stderr chunk (state=%s):\n>>>%s<<<\n" % (state, chunk))

            # We examine the output line-by-line until we have negotiated any
            # privilege escalation prompt and subsequent success/error message.
            # Afterwards, we can accumulate output without looking at it.

            if state < states.index('ready_to_send'):
                if tmp_stdout:
                    output, unprocessed = self._examine_output('stdout', states[state], tmp_stdout, sudoable)
                    stdout += output
                    tmp_stdout = unprocessed

                if tmp_stderr:
                    output, unprocessed = self._examine_output('stderr', states[state], tmp_stderr, sudoable)
                    stderr += output
                    tmp_stderr = unprocessed
            else:
                stdout += tmp_stdout
                stderr += tmp_stderr
                tmp_stdout = tmp_stderr = ''

            # If we see a privilege escalation prompt, we send the password.
            # (If we're expecting a prompt but the escalation succeeds, we
            # didn't need the password and can carry on regardless.)

            if states[state] == 'awaiting_prompt':
                if self._flags['become_prompt']:
                    display.debug('Sending become_pass in response to prompt')
                    stdin.write('{0}\n'.format(to_bytes(self._play_context.become_pass )))
                    self._flags['become_prompt'] = False
                    state += 1
                elif self._flags['become_success']:
                    state += 1

            # We've requested escalation (with or without a password), now we
            # wait for an error message or a successful escalation.

            if states[state] == 'awaiting_escalation':
                if self._flags['become_success']:
                    display.debug('Escalation succeeded')
                    self._flags['become_success'] = False
                    state += 1
                elif self._flags['become_error']:
                    display.debug('Escalation failed')
                    self._terminate_process(p)
                    self._flags['become_error'] = False
                    raise AnsibleError('Incorrect %s password' % self._play_context.become_method)
                elif self._flags['become_nopasswd_error']:
                    display.debug('Escalation requires password')
                    self._terminate_process(p)
                    self._flags['become_nopasswd_error'] = False
                    raise AnsibleError('Missing %s password' % self._play_context.become_method)
                elif self._flags['become_prompt']:
                    # This shouldn't happen, because we should see the "Sorry,
                    # try again" message first.
                    display.debug('Escalation prompt repeated')
                    self._terminate_process(p)
                    self._flags['become_prompt'] = False
                    raise AnsibleError('Incorrect %s password' % self._play_context.become_method)

            # Once we're sure that the privilege escalation prompt, if any, has
            # been dealt with, we can send any initial data and start waiting
            # for output.

            if states[state] == 'ready_to_send':
                if in_data:
                    self._send_initial_data(stdin, in_data)
                state += 1

            # Now we're awaiting_exit: has the child process exited? If it has,
            # and we've read all available output from it, we're done.

            if p.poll() is not None:
                if not rpipes or not rfd:
                    break

                # When ssh has ControlMaster (+ControlPath/Persist) enabled, the
                # first connection goes into the background and we never see EOF
                # on stderr. If we see EOF on stdout and the process has exited,
                # we're probably done. We call select again with a zero timeout,
                # just to make certain we don't miss anything that may have been
                # written to stderr between the time we called select() and when
                # we learned that the process had finished.

                if p.stdout not in rpipes:
                    timeout = 0
                    continue

            # If the process has not yet exited, but we've already read EOF from
            # its stdout and stderr (and thus removed both from rpipes), we can
            # just wait for it to exit.

            elif not rpipes:
                p.wait()
                break

            # Otherwise there may still be outstanding data to read.

        return (p.returncode, stdout, stderr)

    def put_file(self, in_path, out_path):
        super(Connection, self).put_file(in_path, out_path)
        display.vvv(u'PUT {0} TO {1}'.format(in_path, out_path), host=self.machine)

        # Set file permissions prior to transfer so that they will be correct
        # on the container
        try:
            if self.remote_uid is not None:
                os.chown(in_path, self.remote_uid, self.remote_gid or -1)
        except OSError:
            raise AnsibleError('failed to change ownership on file {0} to user {1}'.format(in_path, self._play_context.remote_user))

        out_path = self._prefix_login_path(out_path)
        if not os.path.exists(to_bytes(in_path, errors='strict')):
            raise AnsibleFileNotFound('file or module does not exist: {0}'.format(in_path))

        # Okay, this is definitely not a great idea to do, that's pretty ugly,
        # but we have no choice... Let me explain
        # You cannot "copy-to --force" with machinectl because machine DBus
        # policy misses the corresponding method declaration
        # (CopyToMachineWithFlags). It has been fixed upstream but it is not
        # available yet in distributions:
        # https://github.com/systemd/systemd/commit/02927af799dbca2ca22a652dc9acc692326dbc3f
        #
        # So you cannot overwrite an existing file. This is very annoying when
        # pushing DIRECTORIES... as the same ansible file (with the same name
        # on the remote target) must be overwritten for each file in the
        # directory.
        # Without removing the file first, we get an error: "file exists".
        remove_cmd = self._shell.remove(out_path, recurse=True)
        remove_sh_cmd = [self._play_context.executable, '-c', remove_cmd]
        returncode, stdout, stderr = self._run_command('shell', args=remove_sh_cmd, machine=self.machine)
        if returncode != 0:
            raise AnsibleError('failed to perform cleanup of file {0}:\n{1}\n{2}'.format(out_path, stdout, stderr))
        returncode, stdout, stderr = self._run_command('copy-to', args=[in_path, out_path], machine=self.machine)
        if returncode != 0:
            raise AnsibleError('failed to transfer file {0} to {1}:\n{2}\n{3}'.format(in_path, out_path, stdout, stderr))

    def fetch_file(self, in_path, out_path):
        super(Connection, self).fetch_file(in_path, out_path)
        display.vvv(u'FETCH {0} TO {1}'.format(in_path, out_path), host=self.machine)

        in_path = self._prefix_login_path(in_path)

        returncode, stdout, stderr = self._run_command('copy-from', args=[in_path, out_path], machine=self.machine)

        if returncode != 0:
            raise AnsibleError('failed to transfer file {0} from {1}:\n{2}\n{3}'.format(out_path, in_path, stdout, stderr))

        # TODO might not be necessary?
        # Reset file permissions to current user after transferring from
        # container
        try:
            if self.remote_uid is not None:
                os.chown(out_path, os.geteuid(), os.getegid() or -1)
        except OSError:
            raise AnsibleError('failed to change ownership on file {0} to user {1}'.format(out_path, os.getlogin()))

