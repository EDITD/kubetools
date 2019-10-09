import click

from kubetools_client.cli import cli_bootstrap
from kubetools_client.config import load_kubetools_config
from kubetools_client.kubernetes import generate_kubernetes_configs_for_project


@cli_bootstrap.command(help_priority=2)
def configs():
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

    click.echo('--> Services')
    click.echo(services)

    click.echo()
    click.echo('--> Deployments')
    click.echo(deployments)

    click.echo()
    click.echo('--> Jobs')
    click.echo(jobs)
