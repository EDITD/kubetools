import click

from kubetools_client import __version__
from kubetools_client import KubeClient
from kubetools_client.log import setup_logging
from kubetools_client.settings import get_settings


class SpecialHelpOrder(click.Group):
    def __init__(self, *args, **kwargs):
        self.help_priorities = {}
        super(SpecialHelpOrder, self).__init__(*args, **kwargs)

    def list_commands(self, ctx):
        '''
        Reorder the list of commands when listing the help.
        '''
        commands = super(SpecialHelpOrder, self).list_commands(ctx)
        return (
            c[1] for c in sorted(
                (self.help_priorities.get(command, 1), command)
                for command in commands
            )
        )

    def group(self, *args, **kwargs):
        '''
        Behaves the same as `click.Group.command()` except capture a priority for
        listing command names in help.
        '''

        help_priority = kwargs.pop('help_priority', 1)
        help_priorities = self.help_priorities

        def decorator(f):
            cmd = super(SpecialHelpOrder, self).group(*args, **kwargs)(f)
            help_priorities[cmd.name] = help_priority
            return cmd

        return decorator

    def command(self, *args, **kwargs):
        '''
        Behaves the same as `click.Group.command()` except capture a priority for
        listing command names in help.
        '''

        help_priority = kwargs.pop('help_priority', 1)
        help_priorities = self.help_priorities

        def decorator(f):
            cmd = super(SpecialHelpOrder, self).command(*args, **kwargs)(f)
            help_priorities[cmd.name] = help_priority
            return cmd

        return decorator


@click.group(cls=SpecialHelpOrder)
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
