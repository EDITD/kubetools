import click

from kubetools_client import __version__
from kubetools_client.config import load_kubetools_config
from kubetools_client.log import setup_logging
from kubetools_client.settings import get_settings

from . import backends  # noqa


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

    # Get the config and attach it to the context
    ctx.obj = load_kubetools_config(env=env, dev=True)
