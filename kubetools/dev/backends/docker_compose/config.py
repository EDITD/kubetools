import re

from collections import OrderedDict
from functools import lru_cache
from hashlib import md5
from os import makedirs, path

import click
import yaml

from kubetools.exceptions import KubeDevError
from kubetools.settings import get_settings

NON_COMPOSE_KEYS = (
    # Kubetools specific
    'minKubetoolsVersion',

    # Kubetools dev specific
    'devScripts',
    'containerContext',

    # Kubetools -> Kubernetes specific
    'servicePorts',
    'probes',
    'resources',

    # Kubernetes specific
    'livenessProbe',
    'readinessProbe',

    # Internal flags for `ktd status`
    'is_deployment',
    'is_dependency',
)

CONTAINER_KEYS = ('dependencies', 'deployments')
CONTAINER_KEY_TO_FLAG = {
    'dependencies': 'is_dependency',
    'deployments': 'is_deployment',
}


def dockerise_label(value):
    # Unfortunate egg from Docker engine pre label support, see:
    # https://github.com/docker/compose/issues/2119
    return re.sub(r'[^a-z0-9]', '', value.lower())


def get_project_name(kubetools_config):
    name = kubetools_config['name']
    env = kubetools_config['env']

    # Compose name is APP-ENV
    return '-'.join((name, env))


def get_compose_name(kubetools_config):
    name_env = get_project_name(kubetools_config)
    return dockerise_label(name_env)


def get_compose_dirname(kubetools_config):
    settings = get_settings()
    return path.join(
        path.dirname(kubetools_config['_filename']),
        settings.DEV_CONFIG_DIRNAME,
    )


def get_compose_filename(kubetools_config):
    env = kubetools_config['env']
    compose_filename = '{0}-compose.yml'.format(env)
    return path.join(get_compose_dirname(kubetools_config), compose_filename)


def get_all_containers(kubetools_config, container_keys=CONTAINER_KEYS):
    containers = []

    for key_name in container_keys:
        deployments = kubetools_config.get(key_name, {})

        for deployment_name, deployment_config in deployments.items():
            if 'containers' not in deployment_config:
                raise KubeDevError('Deployment {0} is missing containers'.format(
                    deployment_name,
                ))

            deployment_containers = deployment_config['containers']

            for container_name, config in deployment_containers.items():
                config[CONTAINER_KEY_TO_FLAG[key_name]] = True
                containers.append((container_name, config))

    return containers


def get_all_containers_by_name(kubetools_config, container_keys=CONTAINER_KEYS):
    return OrderedDict(get_all_containers(
        kubetools_config,
        container_keys=container_keys,
    ))


def _create_compose_service(kubetools_config, name, config, envvars=None):
    for invalid_build_key in (
        'preBuildCommands',
        'registry',
    ):
        if invalid_build_key in config.get('build', {}):
            config['build'].pop(invalid_build_key)

    # Because this is one of our containers (buildContexts are relevant to
    # the project) - setup a TTY and STDIN so we can attach and be interactive
    # when attached (eg ipdb).
    service = {
        'tty': True,
        'stdin_open': True,
        'labels': {
            'kubetools.project.name': kubetools_config['name'],
            'kubetools.project.env': kubetools_config['env'],
        },
    }

    service.update(config)

    # Translate k8s command/args to docker-compose entrypoint/command
    if 'command' in service:
        service['entrypoint'] = service.pop('command')
    if 'args' in config:
        service['command'] = service.pop('args')

    if 'build' in service and 'context' not in service['build']:
        service['build']['context'] = '.'

    if 'ports' in config:
        # Generate a consistent base port for this project/container combo
        hash_string = '{0}-{1}'.format(get_project_name(kubetools_config), name)

        # MD5 the string, integer that and then modulus 10k to shorten it down
        port_base = int(md5(hash_string.encode('utf-8')).hexdigest(), 16) % 10000
        # And bump by 10k so we don't stray into the privileged port range (<1025)
        port_base += 10000

        # Reassign ports with explicit host port numbers
        ports = []

        for port in config['ports']:
            if isinstance(port, dict):
                port = port['port']

            ports.append(
                '{0}:{1}'.format(int(port_base) + int(port), port),
            )

        service['ports'] = ports

    # Make our service - drop anything kubernetes or kubetools specific
    service = {
        key: value
        for key, value in service.items()
        if key not in NON_COMPOSE_KEYS
    }

    # Provide project-specific aliases for all containers. This means we can up
    # the same containers (eg mariadb x2) under the same dev network, but have
    # each app speak to it's own mariadb instance (eg app-mariadb).
    compose_name = kubetools_config['name']

    service['networks'] = {
        'default': {
            'aliases': [
                '{0}-{1}'.format(compose_name, name),
            ],
        },
    }

    # Add any *missing* extra envvars
    if envvars:
        environment = service.setdefault('environment', [])
        for envar in envvars:
            if envar not in environment:
                environment.append(envar)

    return service


@lru_cache(maxsize=1)
def get_dev_network_environment_variables():
    # This "fixes" a horrible circular dependency between config/docker_util
    from .docker_util import get_all_docker_dev_network_containers
    containers = get_all_docker_dev_network_containers()

    envvars = set()

    for container in containers:
        networks = container.attrs['NetworkSettings']['Networks']
        if 'dev' not in networks:
            continue

        aliases = networks['dev']['Aliases']
        for alias in aliases:
            if '-' in alias:
                break
        else:  # no alias with "-"
            continue

        envar = alias.upper().replace('-', '_')
        envvars.add('DEV_{0}={1}'.format(envar, alias))
    return list(envvars)


def create_compose_config(kubetools_config):
    # If we're not in a custom env, everything sits on the "dev" network. Envs
    # remain encapsulated inside their own network.
    DEV_DEFAULT_ENV = get_settings().DEV_DEFAULT_ENV
    ktd_env = kubetools_config.get('env', DEV_DEFAULT_ENV)
    dev_network = ktd_env == DEV_DEFAULT_ENV

    all_containers = get_all_containers(kubetools_config)

    envvars = [
        'KTD_ENV={0}'.format(ktd_env),
    ]

    dev_network_envvars = None
    if dev_network:
        dev_network_envvars = get_dev_network_environment_variables()
        if dev_network_envvars:
            envvars.extend(dev_network_envvars)

    click.echo('--> Injecting environment variables:')
    for envar in envvars:
        click.echo('    {0}'.format(envar))

    services = {
        name: _create_compose_service(
            kubetools_config, name, config,
            envvars=envvars,
        )
        for name, config in all_containers
    }

    compose_config = {
        'version': '3',
        'services': services,
    }

    if dev_network:
        compose_config['networks'] = {
            'default': {
                'external': {
                    'name': 'dev',
                },
            },
        }

    yaml_data = yaml.safe_dump(compose_config)

    compose_dirname = get_compose_dirname(kubetools_config)
    if not path.exists(compose_dirname):
        makedirs(compose_dirname)

    with click.open_file(get_compose_filename(kubetools_config), 'w') as f:
        f.write(yaml_data)
