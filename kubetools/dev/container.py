import os

import click

from . import dev
from .backend import (
    build_containers,
    exec_container,
    get_container_status,
    run_container,
)


@dev.command()
@click.argument('container')
@click.option('--shell', default='sh')
@click.pass_obj
def enter(kubetools_config, container, shell):
    '''
    Enter a shell in a running container.
    '''

    click.echo('--> Entering {0}'.format(click.style(container, bold=True)))
    exec_container(kubetools_config, container, [shell])


@dev.command()
@click.argument('container')
@click.pass_obj
def attach(kubetools_config, container):
    '''
    Attach to the main process in a container.
    '''

    container_status = get_container_status(kubetools_config, container)

    click.echo('--> Attaching to {0}'.format(click.style(container, bold=True)))
    click.echo('    use ctrl + p, ctrl + q to escape')

    # We *don't* use run_process here because when you escape the process exits
    # with an error code (go docker).
    os.system('docker attach {0}'.format(container_status['id']))


@dev.command(name='exec')
@click.argument('container')
@click.argument(
    'command',
    nargs=-1,
    required=True,
)
@click.pass_obj
def exec_(kubetools_config, container, command):
    '''
    Run a command in an existing container.
    '''

    click.echo('--> Building any out of date containers')
    build_containers(kubetools_config, [container])
    click.echo()

    click.echo('--> Executing in {0}: {1}'.format(container, command))
    return exec_container(kubetools_config, container, command)


@dev.command()
@click.argument('container')
@click.argument(
    'command',
    nargs=-1,
    required=True,
)
@click.option(
    'envvars', '-e', '--envvar',
    '--envar',  # legacy support TODO: remove!
    multiple=True,
    help='Environment variables to pass into the container.',
)
@click.pass_obj
def run(kubetools_config, container, command, envvars=None):
    '''
    Run a command in a new container.
    '''

    click.echo('--> Building any out of date containers')
    build_containers(kubetools_config, [container])
    click.echo()

    click.echo('--> Running in {0}: {1}'.format(container, command))
    return run_container(kubetools_config, container, command, envvars=envvars)
