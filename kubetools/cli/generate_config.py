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
    '--format', 'output_format',
    type=click.Choice(('json', 'yaml')),
    default='json',
    help='Specify the output format',
)
@click.argument(
    'app_dir',
    type=click.Path(exists=True, file_okay=False),
)
@click.option(
    '--default-registry',
    help='Default registry for apps that do not specify.',
)
@click.pass_context
def config(ctx, replicas, file, app_dir, output_format, default_registry):
    '''
    Generate and write out Kubernetes configs for a project.
    '''

    env = ctx.meta['kube_context']
    kubetools_config = load_kubetools_config(app_dir, env=env, custom_config_file=file)
    context_to_image = defaultdict(lambda: 'IMAGE')
    services, deployments, jobs, cronjobs = generate_kubernetes_configs_for_project(
        kubetools_config,
        replicas=replicas,
        context_name_to_image=context_to_image,
        default_registry=default_registry,
    )

    echo_resources(services, 'Service', output_format)
    echo_resources(deployments, 'Deployment', output_format)
    echo_resources(jobs, 'Job', output_format)
    echo_resources(cronjobs, 'Cronjob', output_format)


def echo_resources(resources, resource_kind, output_format):
    formatter = FORMATTERS[output_format]
    for resource in resources:
        name = get_object_name(resource)
        click.echo(f'{resource_kind}: {click.style(name, bold=True)}')
        click.echo(formatter(resource))
        click.echo()
