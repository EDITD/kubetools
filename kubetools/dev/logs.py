import click

from . import dev
from .backend import (
    follow_logs,
    get_all_containers_by_name,
)

DEFAULT_LOG_LINES = 5


@dev.command()
@click.argument('containers', nargs=-1)
@click.option(
    'all_containers', '--all',
    is_flag=True,
    help='Show the output of all containers, not just app containers',
)
@click.option(
    '-n', '--number-of-lines',
    type=int,
    default=DEFAULT_LOG_LINES,
    help='Number of lines of history to output',
)
@click.option(
    '--with-history',
    is_flag=True,
    help='Show all of the output history rather than `-n` lines',
)
@click.pass_obj
def logs(
    kubetools_config,
    containers, all_containers,
    number_of_lines, with_history,
):
    '''
    Follow logs for the dev environment.
    '''

    click.echo(click.style(
        '--> Following dev environment logs...', 'blue',
    ))

    # Show all the top level containers
    if not containers and not all_containers:
        containers = list(get_all_containers_by_name(
            kubetools_config,
            ('deployments',),
        ).keys())

    tail = number_of_lines
    if with_history:
        # "all" is a special value for `docker-compose logs tail=X`
        tail = 'all'
        if number_of_lines != DEFAULT_LOG_LINES:
            click.echo(click.style(
                '-n={0} overridden by --with-history'.format(number_of_lines),
                'yellow',
            ))

    follow_logs(kubetools_config, containers, tail=tail)
