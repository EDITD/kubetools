import json

from collections import defaultdict

import click

from kubetools.config import load_kubetools_config
from kubetools.kubernetes.api import get_object_name
from kubetools.kubernetes.config import generate_kubernetes_configs_for_project

from . import cli_bootstrap


@cli_bootstrap.command(help_priority=4)
@click.argument(
    'app_dir',
    type=click.Path(exists=True, file_okay=False),
)
@click.pass_context
def config(ctx, app_dir):
    '''
    Generate and write out Kubernetes configs for a project.
    '''

    kubetools_config = load_kubetools_config(app_dir)
    context_to_image = defaultdict(lambda: f'IMAGE')
    services, deployments, jobs = generate_kubernetes_configs_for_project(
        kubetools_config,
        context_name_to_image=context_to_image,
    )

    for service in services:
        name = get_object_name(service)
        click.echo(f'Service: {click.style(name, bold=True)}')
        click.echo(json.dumps(service, indent=4))
        click.echo()

    for deployment in deployments:
        name = get_object_name(deployment)
        click.echo(f'Service: {click.style(name, bold=True)}')
        click.echo(json.dumps(deployment, indent=4))
        click.echo()

    for job in jobs:
        name = get_object_name(job)
        click.echo(f'Service: {click.style(name, bold=True)}')
        click.echo(json.dumps(job, indent=4))
        click.echo()
