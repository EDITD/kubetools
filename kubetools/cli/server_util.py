import os

from collections import deque
from time import sleep

import click


# Hacky way of getting terminal size (so can clear lines)
# Source: http://stackoverflow.com/questions/566746
TERMINAL_SIZE = os.popen('stty size', 'r').read().split()
IS_TTY = bool(TERMINAL_SIZE)
TERMINAL_WIDTH = int(TERMINAL_SIZE[1]) if IS_TTY else None

# Rotate the spinner every 1/UPDATE_DIVISOR seconds
UPDATE_DIVISOR = 20

# Get stdout as defined by Click
STDOUT = click.get_text_stream('stdout')


def _clear_line(return_=True):
    line = ''.join(' ' for _ in range(0, TERMINAL_WIDTH))

    if return_:
        line = '{0}\r'.format(line)

    STDOUT.write(line)
    STDOUT.flush()


def wait_with_spinner(
    func,
    check_status_divisor=UPDATE_DIVISOR,
    tick_divisor=UPDATE_DIVISOR,
):
    wait_chars = deque(('-', '/', '|', '\\'))
    wait_ticks = 0

    # Store previous status so we still print progress w/o a tty, but only when
    # it changes rather than every .05s.
    previous_status = ''

    while True:
        # Get build state every ~1s
        if wait_ticks % check_status_divisor == 0:
            status = func(previous_status)

        # None = complete, so just break the loop
        if status is None:
            break

        status = status.strip()

        # Write status spinner
        if IS_TTY:
            # Limit prefix + status text width to terminal width
            width_limit = TERMINAL_WIDTH - 50
            if len(status) > width_limit:
                status = '{0}...'.format(status[:width_limit])

            _clear_line()
            STDOUT.write('  {0} in progress{1}\r'.format(
                wait_chars[0],
                ' (status = {0})'.format(status) if status else '',
            ))
            STDOUT.flush()
            wait_chars.rotate(1)

        # Print out changes to status only when no tty
        else:
            if status != previous_status:
                click.echo('    status: {0}'.format(status))

        previous_status = status

        # Tick tock
        wait_ticks += 1
        sleep(1 / tick_divisor)

    # This hack clears the progress bar line
    if IS_TTY:
        _clear_line()
