from os import environ, path

import click

from kubetools.exceptions import KubeDevError
from kubetools.settings import get_settings, get_settings_directory

from . import dev
from .backend import (
    get_all_containers,
    get_all_containers_by_name,
    get_container_status,
)
from .process_util import run_process


def _list_scripts(kubetools_config):
    '''
    List available dev scripts.
    '''

    settings = get_settings()
    click.echo('--> Containers & scripts:')

    for name, container in get_all_containers(kubetools_config):
        if 'devScripts' not in container:
            continue

        click.echo('    {0}:'.format(click.style(name, bold=True)))

        for script in container['devScripts']:
            if script in settings.scripts:
                click.echo('    - {0}'.format(click.style(script, 'green')))
            else:
                click.echo('    - {0} (not found)'.format(
                    click.style(script, 'red'),
                ))


@dev.command()
@click.argument('container', required=False)
@click.argument('script', required=False)
@click.pass_obj
def script(kubetools_config, container=None, script=None):
    '''
    List and execute scripts.

    The script must be made available to the container in `kubetools.yml`.
    '''

    if container is None or script is None:
        return _list_scripts(kubetools_config)

    settings = get_settings()
    config = get_all_containers_by_name(kubetools_config).get(container)

    if not config:
        raise KubeDevError('Invalid container: {0}'.format(container))

    if script not in config.get('devScripts', []):
        raise KubeDevError('Script {0} is not available in container {1}'.format(
            script, container,
        ))

    script_path = path.join(get_settings_directory(), 'scripts', script)

    if script not in settings.scripts:
        raise KubeDevError('Could not locate local script (expected: {0})'.format(
            script_path,
        ))

    status = get_container_status(kubetools_config, container)
    if not status or not status['up']:
        raise KubeDevError('Container {0} is not online'.format(container))

    script_env = environ.copy()
    script_env['APP_NAME'] = kubetools_config['name']

    # Add the envvars defined in kubetools.yml
    for env in config.get('environment', []):
        key, value = env.split('=', 1)
        script_env[key] = value

    # Add PORT_N envvars mapping the container -> host ports
    for port in status['ports']:
        # Remove the /tcp, /udp bit
        local_port = port['local'].replace('/', '')
        host_port = port['host'].split(':')[-1]
        script_env['PORT_{0}'.format(local_port)] = host_port

    # Execute the script!
    run_process([script_path], env=script_env, capture_output=False)
