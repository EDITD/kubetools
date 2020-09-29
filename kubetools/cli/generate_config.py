import json

from collections import defaultdict

import click
import yaml

from kubetools.config import load_kubetools_config
from kubetools.kubernetes.api import get_object_name
from kubetools.kubernetes.config import generate_kubernetes_configs_for_project

from . import cli_bootstrap


yaml.Dumper.ignore_aliases = lambda *args: True

FORMATTERS = {
    'json': lambda d: json.dumps(d, indent=4),
    'yaml': lambda d: yaml.dump(d),
}


@cli_bootstrap.command(help_priority=4)
@click.option(
    '--replicas',
    type=int,
    default=1,
    help='Default number of replicas for each app.',
)
@click.option(
    '-f', '--file',
    nargs=1,
    help='Specify a non-default Kubetools yml file to generate config from.',
    type=click.Path(exists=True),
)
@click.option(
    '--format', 'formatter',
    type=click.Choice(('json', 'yaml')),
    default='json',
    help='Specify the output format',
)
@click.argument(
    'app_dir',
    type=click.Path(exists=True, file_okay=False),
)
@click.pass_context
def config(ctx, replicas, file, app_dir, formatter):
    '''
    Generate and write out Kubernetes configs for a project.
    '''

    kubetools_config = load_kubetools_config(app_dir, custom_config_file=file)
    context_to_image = defaultdict(lambda: 'IMAGE')
    services, deployments, jobs = generate_kubernetes_configs_for_project(
        kubetools_config,
        replicas=replicas,
        context_name_to_image=context_to_image,
    )

    writer = FORMATTERS[formatter]

    for service in services:
        name = get_object_name(service)
        click.echo(f'Service: {click.style(name, bold=True)}')
        click.echo(writer(service))
        click.echo()

    for deployment in deployments:
        name = get_object_name(deployment)
        click.echo(f'Deployment: {click.style(name, bold=True)}')
        click.echo(writer(deployment))
        click.echo()

    for job in jobs:
        name = get_object_name(job)
        click.echo(f'Job: {click.style(name, bold=True)}')
        click.echo(writer(job))
        click.echo()
