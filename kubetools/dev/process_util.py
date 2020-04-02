import re

from subprocess import CalledProcessError, PIPE, Popen, STDOUT
from threading import Thread

from kubetools.cli.server_util import UPDATE_DIVISOR, wait_with_spinner
from kubetools.exceptions import KubeDevCommandError
from kubetools.log import logger
from kubetools.settings import get_settings


def _read_command_output(command, output_lines):
    # Read the commands output indefinitely
    while True:
        stdout_line = command.stdout.readline()

        if stdout_line:
            # Remove any trailing newline
            stdout_line = stdout_line.decode().strip('\n')
            # # Strip non-alphanumeric  characters
            # stdout_line = re.sub(r'[^a-zA-Z0-9_\.\-\s]', '', stdout_line)

            # Strip any ANSI escape characters
            stdout_line = re.sub(
                r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]',
                '',
                stdout_line,
            )

            output_lines.append(stdout_line)

        # No line from the command? We're done!
        else:
            break


def _run_process_with_spinner(args):
    command = Popen(
        ' '.join(args),
        stdout=PIPE,
        stderr=STDOUT,
        close_fds=True,
        shell=True,
    )

    # Buffers
    output_lines = []

    command_reader = Thread(
        target=_read_command_output,
        args=(command, output_lines),
    )
    command_reader.start()

    def check_status(previous_status):
        # Command complete (we've read everything)? Exit here
        if not command_reader.is_alive():
            return

        if output_lines:
            return output_lines[-1]

        return previous_status

    wait_with_spinner(
        check_status,
        # This means we run the get_line check every .5 seconds
        check_status_divisor=(UPDATE_DIVISOR / 2),
    )

    # Re-join the stdout/stderr lines
    stdout = '\n'.join(output_lines)

    # Poll the command to populate it's return code
    command.poll()

    # Ensure the command is dead
    try:
        command.terminate()
        command.kill()

    # If already dead, just ignore
    except Exception:
        pass

    return command.returncode, stdout


def run_process(args, env=None, capture_output=None):
    settings = get_settings()

    capturing_output = False

    if (
        # If we explicitly need to capture, always capture
        capture_output
        # Otherwise, capture if we're not --debug and not explicitly no capture
        or (settings.debug == 0 and capture_output is not False)
    ):
        capturing_output = True

    logger.debug('--> Executing: {0}'.format(' '.join(args)))

    try:
        # If we're capturing output - things are more complicated. We need to spawn
        # the subprocess in a thread and read its output into two lists, which we
        # then rejoin to return.
        if capturing_output:
            code, stdout = _run_process_with_spinner(args)

        # Inline? Simply start the process and "communicate", this will print stdout
        # and stderr to the terminal and also capture them into variables.
        else:
            command = Popen(args, env=env, stderr=STDOUT, close_fds=True)
            stdout, _ = command.communicate()
            code = command.returncode

        if code > 0:
            raise KubeDevCommandError(
                'External process failed: {0}'.format(args),
                stdout,
            )

        return stdout

    except (CalledProcessError, OSError) as e:
        raise KubeDevCommandError(
            'External process failed: {0}'.format(args),
            getattr(e, 'output', e),
        )
