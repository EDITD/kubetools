import click

from kubernetes import config

from kubetools import __version__
from kubetools.log import setup_logging
from kubetools.settings import get_settings


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


def _get_context_names():
    try:
        contexts, active_context = config.list_kube_config_contexts()
    except config.ConfigException as e:
        # The python-kubernetes library currently does not handle a missing "current context"
        # well at all, raising an exception.
        # See: https://github.com/kubernetes-client/python/issues/1193
        if 'Expected key current-context' in e.args[0]:
            raise click.ClickException((
                'No current-context set in kubeconfig! Please set this to any '
                'value using `kubectl config use-context <name>`.'
            ))
        raise

    if not contexts:
        print('Cannot find any context in kube-config file.')
        return
    return [context['name'] for context in contexts], active_context['name']


def print_contexts(ctx, param, value):
    if not value:
        return

    click.echo('--> Available Kubernetes contexts:')
    context_names, active_context_name = _get_context_names()
    for name in context_names:
        click.echo(f'    {click.style(name, bold=name == active_context_name)}')

    ctx.exit()


def ensure_context(ctx, param, value):
    context_names, active_context_name = _get_context_names()

    if value:
        if value not in context_names:
            raise click.BadParameter(f'{value}; available contexts: {context_names}')
    else:
        click.echo(f'Using active context: {click.style(active_context_name, bold=True)}')
        value = active_context_name

    return value


@click.group(cls=SpecialHelpOrder)
@click.option(
    '--context',
    callback=ensure_context,
    envvar='KUBETOOLS_CONTEXT',
    help='The name of the Kubernetes context to use.',
)
@click.option(
    '--contexts',
    is_flag=True,
    is_eager=True,
    callback=print_contexts,
    expose_value=False,
    help='List available Kubernetes contexts and exit.',
)
@click.option('--debug', is_flag=True, help='Show debug logs.')
@click.version_option(version=__version__, message='%(prog)s: v%(version)s')
@click.pass_context
def cli_bootstrap(ctx, context, debug):
    '''
    Kubetools client - deploy apps to Kubernetes.
    '''

    ctx.meta['kube_context'] = context

    setup_logging(debug)
    get_settings()
