import json

import click

from kubetools_client.cli import cli_bootstrap
from kubetools_client.config import load_kubetools_config
from kubetools_client.kubernetes import generate_kubernetes_configs_for_project


@cli_bootstrap.command(help_priority=2)
@click.option('--pretty', is_flag=True, help='Pretty print the generated configs')
def configs(pretty):
    '''
    Generate & dump kubernetes configs.
    '''

    kubetools_config = load_kubetools_config()

    context_to_image = {}  # make a fake context name -> image mapping
    for context_name in kubetools_config.get('containerContexts'):
        context_to_image[context_name] = 'CONTEXT_IMAGE_{0}'.format(context_name)

    services, deployments, jobs = generate_kubernetes_configs_for_project(
        kubetools_config,
        context_name_to_image=context_to_image,
    )

    click.echo('### Kubernetes configs for project: {0}'.format(
        click.style(kubetools_config['name'], bold=True),
    ))
    click.echo()

    def print_json(obj):
        if pretty:
            data = json.dumps(obj, indent=4)
        else:
            data = json.dumps(obj)

        click.echo(data)

    click.echo('--> Services')
    click.echo(print_json(services))

    click.echo()
    click.echo('--> Deployments')
    click.echo(print_json(deployments))

    click.echo()
    click.echo('--> Jobs')
    click.echo(print_json(jobs))
