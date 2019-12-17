import os

from time import sleep

import click
import requests

from pyretry import retry

from kubetools.exceptions import KubeDevError
from kubetools.log import logger
from kubetools.settings import get_settings

from .config import (
    get_all_containers,
    get_all_containers_by_name,
)
from .docker_util import (
    ensure_docker_dev_network,
    get_container_status,
    get_containers_status,
    run_compose_process,
)


def init_backend():
    ensure_docker_dev_network()


def http_get(url, timeout):
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

    except requests.RequestException as e:
        raise KubeDevError('Container start failed HTTP check: {0}'.format(e))


def find_container_for_config(kubetools_config, config):
    dockerfile = config['build']['dockerfile']
    all_containers = get_all_containers(kubetools_config)

    for name, container in all_containers:
        if container.get('build', {}).get('dockerfile') == dockerfile:
            return name
    else:
        raise KubeDevError((
            'No container found using Dockerfile: {0}'
        ).format(dockerfile))


def _build_container(kubetools_config, name, dockerfile):
    container_status = get_containers_status(kubetools_config)

    # Skip if the container is already up
    if name in container_status and container_status[name]['up']:
        return

    run_compose_process(
        kubetools_config,
        ('build', '--pull', name),
    )


def build_containers(kubetools_config, names=None):
    all_containers = get_all_containers(kubetools_config)

    # Filter list of containers to build if specified
    if names:
        all_containers = [
            (name, container)
            for name, container in all_containers
            if name in names
        ]

    seen_dockerfiles = set()

    for name, config in all_containers:
        # Skip any image based containers
        if 'image' in config:
            continue

        dockerfile = config['build']['dockerfile']

        # Don't print the same `preBuildCommands` over and over!
        if dockerfile not in seen_dockerfiles:
            click.echo('--> Updating {0}'.format(dockerfile))

            pre_build_commands = config['build'].get('preBuildCommands')
            if pre_build_commands:
                click.echo('{0}: {1}:'.format(
                    click.style('Note', bold=True),
                    click.style((
                        'There are `preBuildCommands` specified for building '
                        '{0} which have not been executed'
                    ).format(dockerfile), 'yellow'),
                ))

                for command in pre_build_commands:
                    click.echo(' '.join(command))

        seen_dockerfiles.add(dockerfile)
        _build_container(kubetools_config, name, dockerfile)


def _up_container(kubetools_config, name):
    containers_status = get_containers_status(kubetools_config)

    # Skip if the container is already up
    if name in containers_status and containers_status[name]['up']:
        return

    # Up the container in the background
    run_compose_process(
        kubetools_config,
        ('up', '-d', name),
        capture_output=False,
    )

    # Get the new status of the container
    status = get_container_status(kubetools_config, name)

    if not status['up']:
        raise KubeDevError('Container {0} did not start properly'.format(
            click.style(name, bold=True),
        ))


def _probe_container(kubetools_config, name):
    settings = get_settings()

    containers = get_all_containers_by_name(kubetools_config)
    config = containers[name]

    status = get_container_status(kubetools_config, name)

    # Check for readinessProbe or probes (probes = readiness + liveness)
    probe = config.get('readinessProbe', config.get('probes'))
    if probe:
        timeout = probe.get('timeoutSeconds', 5)
        retries = probe.get('failureThreshold', 5)

        # Execute a command to check for container up?
        if 'exec' in probe:
            ready_command = probe['exec']['command']

            click.echo('--> Waiting for {0} to be ready with {1} (timeout={2}, retries={3})'.format(
                name, click.style(' '.join(ready_command), bold=True), timeout, retries,
            ))

            command = ['exec', '-T', name]
            command.extend(ready_command)

            run_with_retry = retry(
                KubeDevError,
                num_retries=retries,
                timeout=timeout,
            )(run_compose_process)

            run_with_retry(kubetools_config, command)

        # Check HTTP status to check for container up?
        if 'httpGet' in probe:
            http_path = probe['httpGet'].get('path', '/')

            click.echo((
                '--> Waiting for {0} to be ready with HTTP GET '
                '{1} (timeout={2}, retries={3})'
            ).format(
                name, click.style(http_path, bold=True), timeout, retries,
            ))

            http_port = probe['httpGet'].get('port', 80)
            tcp_port = '{0}/tcp'.format(http_port)

            # Find the localhost port # matching the containers HTTP port
            target_port = None
            for port in status['ports']:
                if port['local'] == tcp_port:
                    target_port = port['host']
                    break

            http_url = 'http://{0}:{1}{2}'.format(
                settings.DEV_HOST, target_port, http_path,
            )

            get_with_retry = retry(
                KubeDevError,
                num_retries=retries,
                timeout=timeout,
            )(http_get)

            logger.debug('Executing HTTP check: {0}'.format(http_url))
            get_with_retry(http_url, timeout)

    # No probe? Sleep 2s and check it's still up as a super basic check
    else:
        sleep(2)

        # Get the new status of the container
        status = get_container_status(kubetools_config, name)

        if not status['up']:
            raise KubeDevError('Container {0} did not stay up for >2s'.format(
                click.style(name, bold=True),
            ))


def up_containers(kubetools_config, names=None):
    all_containers = get_all_containers(kubetools_config)

    # Filter matching containers if specified
    if names:
        all_containers = [
            (name, container)
            for name, container in all_containers
            if name in names
        ]

    # Up & probe all the containers in order
    for name, _ in all_containers:
        _up_container(kubetools_config, name)
        _probe_container(kubetools_config, name)


def destroy_containers(kubetools_config, names=None):
    containers_status = get_containers_status(kubetools_config)

    if containers_status:
        # Shortcut: bring the entire environment down
        if not names:
            return run_compose_process(
                kubetools_config,
                ('down', '--remove-orphans'),
                capture_output=False,
            )

    all_containers = get_all_containers(kubetools_config)

    # Filter matching containers if specified
    if names:
        all_containers = [
            (name, container)
            for name, container in all_containers
            if name in names
        ]

    for name, config in all_containers:
        run_compose_process(
            kubetools_config,
            ('rm', '--stop', '--force', name),
            capture_output=False,
        )


def start_containers(kubetools_config, names=None):
    containers_status = get_containers_status(kubetools_config)

    # Check each container is stopped
    if names:
        for name in names:
            container_status = containers_status.get(name)

            if not container_status or container_status['up'] is None:
                raise KubeDevError((
                    'Container {0} does not exist and so cannot be started, '
                    'please create it with `ktd up {0}`.'.format(name)
                ))

    # Get the list of stopped containers
    else:
        names = [
            name
            for name, status in containers_status.items()
            # Check for both started & stopped - we only want to warn about
            # containers that don't exist (for ktd up).
            if status['up'] in (True, False)
        ]

        if not names:
            raise KubeDevError((
                'No stopped containers found, '
                'please use `ktd up` to create new containers.'
            ))

    # Start the stopped containers
    run_compose_process(
        kubetools_config,
        ('start',) + tuple(names),
        capture_output=False,
    )


def stop_containers(kubetools_config, names=None):
    # Stop everything?
    if not names:
        # Bring the entire environment stop
        run_compose_process(
            kubetools_config,
            ('stop',),
            capture_output=False,
        )

        return

    containers_status = get_containers_status(kubetools_config)

    # Stop just these containers
    for name in names:
        container_status = containers_status.get(name)

        if container_status and container_status['up']:
            # Stop just this container
            run_compose_process(
                kubetools_config,
                ('stop', name),
                capture_output=False,
            )


def run_container(kubetools_config, container, command, envvars=None):
    compose_command = ['run']

    if envvars:
        compose_command.extend(['-e{0}'.format(e) for e in envvars])

    compose_command.append(container)
    compose_command.extend(command)

    run_compose_process(
        kubetools_config,
        compose_command,
        capture_output=False,
    )


def exec_container(kubetools_config, container, command):
    compose_command = ['exec', container]
    compose_command.extend(command)

    run_compose_process(
        kubetools_config,
        compose_command,
        capture_output=False,
    )


def follow_logs(kubetools_config, containers, tail='all'):
    # Set this so we don't error and exit after 60s inactivity - which is the
    # ridiclous default value set by the docker-compose team.
    os.environ['COMPOSE_HTTP_TIMEOUT'] = '86400'

    args = ['logs', '--follow', '--tail={0}'.format(tail)]

    if containers:
        args.extend(containers)

    run_compose_process(kubetools_config, args, capture_output=False)


def _print_containers(containers):
    container_infos = []
    settings = get_settings()

    for name, data in containers.items():
        port_strings = []

        for port in data['ports']:
            host_address = '{0}:{1}'.format(settings.DEV_HOST, port['host'])

            if port['local'] == '80/tcp':
                host_address = 'http://{0}'.format(host_address)

            port_strings.append(' / {0} -> {1}'.format(port['local'], host_address))

        link_text = ''.join(port_strings)

        if data['up'] is True:
            status_text = click.style('RUNNING', 'green')
        elif data['up'] is False:
            status_text = click.style('STOPPED', 'yellow')
        else:
            status_text = click.style('NOEXIST', 'red', bold=True)

        container_infos.append((
            name,
            '  - [{0}] {1}{2}{3}'.format(
                status_text,
                click.style(name, bold=True),
                ' (dependency)' if data.get('is_dependency') else '',
                link_text,
            ),
        ))

    # Sort alphabetically and print
    container_infos = sorted(
        container_infos,
        key=lambda c: '' if 'dependency' in c[1] else c[0],
    )
    for _, text in container_infos:
        click.echo(text)


def print_containers(kubetools_config, all_environments=False):
    envs_or_containers = get_containers_status(
        kubetools_config,
        all_environments=all_environments,
    )

    if all_environments:
        env_or_container_items = sorted(
            envs_or_containers.items(),
            key=lambda item: item[0] == kubetools_config['env'],
        )

        for i, (env, containers) in enumerate(env_or_container_items, 1):
            click.echo(click.style(
                '--> "{0}" environment state: (--env {0}{1})'.format(
                    env,
                    ', active' if env == kubetools_config['env'] else '',
                ),
                'blue',
            ))
            _print_containers(containers)

            if i < len(envs_or_containers):
                print()
    else:
        click.echo(click.style(
            '--> "dev" environment state:',
            'blue',
        ))
        _print_containers(envs_or_containers)
        containers = envs_or_containers

    # Print up/start messages depending on the container statuses
    up_statuses = [
        container['up']
        for container in containers.values()
    ]

    if None in up_statuses or False in up_statuses:
        click.echo()

    if None in up_statuses:
        click.echo(click.style(
            "Some containers don't exist, create them with: {0}".format(
                click.style('ktd up <container>', bold=True),
            ),
            'yellow',
        ))

    if False in up_statuses:
        click.echo(click.style(
            'Some containers are stopped; start them with: {0}'.format(
                click.style('ktd start <container>', bold=True),
            ),
            'yellow',
        ))
