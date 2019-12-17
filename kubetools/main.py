#!/usr/bin/env python

import sys

import click

from .exceptions import KubeDevCommandError, KubeDevError, KubeError
from .log import logger
from .settings import get_settings


def run_cli(func):
    try:
        func()

    except KubeDevCommandError as e:
        message, stdout = e.args

        click.echo('--> {0} {1}'.format(
            click.style('Kubetools dev exception:', 'red', bold=True),
            message,
        ))
        click.echo(stdout)
        sys.exit(1)

    except KubeDevError as e:
        click.echo('--> {0} {1}'.format(
            click.style('Kubetools dev exception:', 'red', bold=True),
            e,
        ))
        sys.exit(1)

    except KubeError as e:
        if e.type == 'auth':
            settings = get_settings()

            logger.warning((
                'You are not logged into Kubetools!\n'
                'You need to login to your server, download the config '
                'from the top right and save it to:\n{0}\n'
            ).format(settings.filename))

        click.echo('--> {0} {1}'.format(
            click.style('Kubetools {0} exception:'.format(e.type), 'red', bold=True),
            e,
        ))
        sys.exit(1)

    except KeyboardInterrupt:
        click.echo()
        click.echo('Exiting on user request...')

    except Exception as e:
        click.echo('--> Unexpected exception: {0}'.format(
            click.style(
                '{0}{1}'.format(e.__class__.__name__, e.args),
                'red',
                bold=True,
            ),
        ))

        raise
