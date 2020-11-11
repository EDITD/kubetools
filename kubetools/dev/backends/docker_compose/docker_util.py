from functools import lru_cache

import docker
import requests

from kubetools.dev.process_util import run_process
from kubetools.exceptions import KubeDevError
from kubetools.log import logger

from .config import (
    create_compose_config,
    dockerise_label,
    get_all_containers,
    get_compose_filename,
    get_compose_name,
)


@lru_cache(maxsize=1)
def get_docker_client():
    client = docker.from_env()

    try:
        client.ping()

    except (docker.errors.APIError, requests.exceptions.ConnectionError) as e:
        raise KubeDevError((
            'Could not connect to Docker, is it running?\n'
            'Error: {0}'
        ).format(e))

    return client


def ensure_docker_dev_network():
    '''
    Ensure we have a dev Docker network for all our containers to belong to.
    '''

    docker_client = get_docker_client()

    network_names = [
        network.name
        for network in docker_client.networks.list()
    ]

    if 'dev' not in network_names:
        docker_client.networks.create('dev')


def get_all_docker_dev_network_containers():
    '''
    Gets the container names for everything using the global dev network.

    Note only containers created with the default "dev" env become part of this
    network - any custom env (eg when testing or `--env`) won't be included.
    '''

    docker_client = get_docker_client()

    labels = [
        # Ignore containers created by run/exec/etc (not services)
        'com.docker.compose.oneoff=False',
        # Load anything from a compose project
        'com.docker.compose.project',
    ]

    docker_containers = docker_client.containers.list(all=True, filters={
        'label': labels,
    })

    return docker_containers


def get_containers_status(
    kubetools_config,
    container_name=None,
    all_environments=False,
):
    '''
    Get the status of any containers for the current Kubetools project.
    '''

    docker_client = get_docker_client()

    labels = [
        # Ignore containers created by run/exec/etc (not services)
        'com.docker.compose.oneoff=False',
    ]

    if all_environments:
        # Filter by *any* docker compose - we filter out containers that don't
        # belong to this project below - this maintains compatability with
        # kubetools <8 that didn't write the kubetools.project.env label.
        labels.append('com.docker.compose.project')
    else:
        # Filter by the project/env name to only fetch this envs containers
        labels.append('com.docker.compose.project={0}'.format(
            get_compose_name(kubetools_config),
        ))

    if container_name:
        labels.append(
            'com.docker.compose.service={0}'.format(container_name),
        )

    logger.debug('Listing Docker containers with labels={0}'.format(labels))
    docker_containers = docker_client.containers.list(all=True, filters={
        'label': labels,
    })

    env_to_containers = {}
    docker_name = dockerise_label(kubetools_config['name'])

    for container in docker_containers:
        compose_project = container.labels['com.docker.compose.project']
        if all_environments:
            if not compose_project.startswith(docker_name):
                continue

            # For old Kubetools versions (<8) this label won't exist
            kubetools_name = container.labels.get('kubetools.project.name')
            if kubetools_name and kubetools_config['name'] != kubetools_name:
                continue

        env = container.labels.get('kubetools.project.env')
        # Compatability for existing containers created with kubetools <8
        if not env:
            env = compose_project.replace(docker_name, '')

        # Where the name is compose-name_container_N, get container
        name = container.name.split('_')[1]

        status = container.status == 'running'
        ports = []

        if container.attrs['NetworkSettings']['Ports']:
            for (
                local_port, host_port,
            ) in container.attrs['NetworkSettings']['Ports'].items():
                if not host_port:
                    continue

                ports.append({
                    'local': local_port,
                    'host': host_port[0]['HostPort'],
                })

        container_data = {
            'up': status,
            'ports': ports,
            'id': container.id,
            'labels': container.labels,
        }

        env_containers = env_to_containers.setdefault(env, {})

        if name in env_containers:
            raise ValueError((
                'Duplicate container for env {0}!: {1}({2})'
            ).format(env, name, container_data))

        env_containers[name] = container_data

    # Always provide the current environment, even if it's empty
    current_env = kubetools_config['env']
    if current_env not in env_to_containers:
        env_to_containers[kubetools_config['env']] = {}

    for env, containers in env_to_containers.items():
        for name, container in get_all_containers(kubetools_config):
            if name not in containers:
                containers[name] = {
                    'up': None,
                    'id': None,
                    'ports': [],
                }

            containers[name]['is_dependency'] = container.get('is_dependency', False)
            containers[name]['is_deployment'] = container.get('is_deployment', False)

    if all_environments:
        return env_to_containers
    return env_to_containers.get(kubetools_config['env'], {})


def get_container_status(kubetools_config, name):
    containers = get_containers_status(kubetools_config, container_name=name)
    return containers.get(name)


def run_compose_process(kubetools_config, command_args, **kwargs):
    # Ensure we have a compose file for this config
    create_compose_config(kubetools_config)

    compose_command = [
        'docker-compose',
        # Force us to look at the current directory, not relative to the compose
        # filename (ie .kubetools/compose-name.yml).
        '--project-directory', '.',
        # Name of the project (for the com.docker.compose.projectname label)
        '--project-name', get_compose_name(kubetools_config),
        # Filename of the YAML file to load
        '--file', get_compose_filename(kubetools_config),
    ]
    compose_command.extend(command_args)

    return run_process(compose_command, **kwargs)
