import click

from kubetools_client import __version__
from kubetools_client.log import setup_logging
from kubetools_client.settings import get_settings

from .config import get_kubetools_config
from .docker_util import ensure_docker_dev_network


@click.group()
@click.option(
    '--env',
    envvar='KUBETOOLS_DEV_ENV',
    default=None,
    help='Override environment name.',
)
@click.option('--debug', is_flag=True)
@click.version_option(version=__version__, message='%(prog)s: v%(version)s')
@click.pass_context
def dev(ctx, env, debug=False):
    '''
    Kubetools dev client (ktd).
    '''

    setup_logging(debug)

    # Get/setup settings
    settings = get_settings(debug)

    if not env:
        env = settings.DEV_DEFAULT_ENV

    # Always ensure this before running any dev command
    ensure_docker_dev_network()

    # Get the config and attach it to the context
    ctx.obj = get_kubetools_config(env=env)
