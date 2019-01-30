import click

from kubetools_client import __version__
from kubetools_client import KubeClient
from kubetools_client.log import setup_logging
from kubetools_client.settings import get_settings


@click.group()
@click.option(
    '-s', '--server',
    envvar='KUBETOOLS_HOST',
)
@click.option(
    '-p', '--port',
    type=int,
    envvar='KUBETOOLS_PORT',
)
@click.option('kube_env', '--env', '--kube-env')
@click.option('--debug', is_flag=True)
@click.version_option(version=__version__, message='%(prog)s: v%(version)s')
@click.pass_context
def cli_bootstrap(ctx, server=None, port=None, kube_env=None, debug=False):
    '''
    Kubetools client.
    '''

    setup_logging(debug)

    # Get settings
    settings = get_settings(debug)

    # CLI options > settings
    host = server or settings.KUBETOOLS_HOST
    port = port or settings.KUBETOOLS_PORT
    kube_env = kube_env or settings.DEFAULT_KUBE_ENV

    # Setup the client
    ctx.obj = KubeClient(host=host, port=port, kube_env=kube_env)
