'''
Shared Python module for handling Kubetools (kubetools.yml) config. Used by both
the dev client (ktd) and the server (lists KubetoolsClient as a requirement).
'''

from os import getcwd, path

import yaml

from pkg_resources import parse_version

from . import __version__
from .exceptions import KubeConfigError


# Config keys that can be filtered with a conditions: object
TOP_LEVEL_CONDITION_KEYS = (
    'upgrades',
    'deployments',
    'dependencies',
)

# Config keys that can have re-usable containerContext: names
TOP_LEVEL_CONTAINER_KEYS = TOP_LEVEL_CONDITION_KEYS + (
    'tests',
)


def load_kubetools_config(
    directory=None,
    app_name=None,
    # Filters for config items
    env=None,
    namespace=None,
    dev=False,  # when true disables env/namespace filtering (dev *only*)
):
    '''
    Load Kubetools config files.

    Filtering:
        Most config items (deployments, dependencies, upgrades) can have conditions
        attached to them (eg dev: true). If an item has conditions, *either* dev or
        both env/namespace must match.

    Args:
        directory (str): directory to load ther config from (defaults to cwd)
        app_name (str): name of the app we're trying to load
        env (str): which envrionment to filter the config items by
        namespace (str): which namespace to filter the config items by
        dev (bool): filter config items by dev mode
    '''

    possible_filenames = (
        'kubetools.yml',
        'kubetools.yaml',
    )

    if directory:
        possible_files = [
            path.join(directory, filename)
            for filename in possible_filenames
        ]
    else:
        directory = getcwd()
        possible_files = []

        # Attempt parent directories back up to root
        while True:
            possible_files.extend([
                path.join(directory, filename)
                for filename in possible_filenames
            ])

            directory, splitdir = path.split(directory)
            if not splitdir:
                break

    config = None

    for filename in possible_files:
        try:
            with open(filename, 'r') as f:
                config = f.read()

        except IOError:
            pass
        else:
            break

    # If not present, this app deosn't support deploy/upgrade jobs (build/run only)
    if config is None:
        raise KubeConfigError((
            'Could not build app{0} as no kubetools config found!'
        ).format(' ({0})'.format(app_name) if app_name else ''))

    config = yaml.load(config)

    # Check Kubetools version?
    if 'minKubetoolsVersion' in config:
        _check_min_version(config)

    # Apply an env name?
    if env:
        config['env'] = env

    # Filter out config items according to our conditions
    for key in TOP_LEVEL_CONDITION_KEYS:
        if key in config:
            config[key] = _filter_config_data(
                key, config[key],
                env=env,
                namespace=namespace,
                dev=dev,
            )

    # De-nest/apply any contextContexts
    for key in TOP_LEVEL_CONTAINER_KEYS:
        contexts = config.get('containerContexts', {})

        if key in config:
            config[key] = _expand_containers(
                key, config[key],
                contexts=contexts,
                dev=dev,
            )

    return config


def _check_min_version(config):
    running_version = parse_version(__version__)
    needed_version = parse_version(
        # Version must be a string
        str(config['minKubetoolsVersion']),
    )

    if needed_version > running_version:
        raise KubeConfigError(
            'Minimum Kubetools version not met, need {0} but got {1}'.format(
                needed_version, running_version,
            ),
        )


def _filter_config_data(key, items_or_object, env, namespace, dev):
    def is_match(item):
        return _conditions_match(
            item.get('conditions'),
            env=env,
            namespace=namespace,
            dev=dev,
        )

    if isinstance(items_or_object, list):
        return [
            item for item in items_or_object
            if is_match(item)
        ]

    elif isinstance(items_or_object, dict):
        return {
            key: item
            for key, item in items_or_object.items()
            if is_match(item)
        }

    else:
        raise KubeConfigError('Invalid type ({0}) for key: {1}'.format(
            type(items_or_object),
            key,
        ))


def _conditions_match(conditions, env, namespace, dev):
    # Remove any test condition - this isn't actually part of the matching as is
    # only considered in development under `ktd test`.
    if conditions:
        conditions.pop('test', None)

    # No conditions? We're good!
    if conditions is None:
        return True

    # Dev mode? Must have dev: true (or no conditions above)
    if dev:
        return conditions.get('dev') is True

    # If dev is set and nothing else, fail (dev only)!
    if conditions.get('dev') and len(conditions) == 1:
        return False

    # If we have envs but our env isn't present, fail!
    if 'envs' in conditions and env not in conditions['envs']:
        return False

    # We have namespaces but our namespace isn't present, fail!
    if 'namespaces' in conditions and namespace not in conditions['namespaces']:
        return False

    # If we have notNamespaces and our namespace is present, fail!
    if 'notNamespaces' in conditions and namespace in conditions['notNamespaces']:
        return False

    return True


def _expand_containers(key, items_or_object, contexts, dev):
    def do_expand(item):
        return _expand_container(
            item,
            contexts=contexts,
            dev=dev,
        )

    # List items have conditions and containerContext at the same level
    if isinstance(items_or_object, list):
        return [
            do_expand(item)
            for item in items_or_object
        ]

    # Named items have conditions top level. but containers are nested
    elif isinstance(items_or_object, dict):
        new_item = {}

        for key, item in items_or_object.items():
            if 'containers' in item:
                item['containers'] = {
                    k: do_expand(v)
                    for k, v in item.pop('containers').items()
                }

            new_item[key] = item

        return new_item

    else:
        raise KubeConfigError('Invalid type ({0}) for key: {1}'.format(
            type(items_or_object),
            key,
        ))


def _merge_config(base_config, new_config):
    for key, value in new_config.items():
        # If this key is a dict in the old config, merge those
        if key in base_config and isinstance(value, dict):
            _merge_config(base_config[key], new_config[key])
        else:
            base_config[key] = new_config[key]


def _expand_container(container, contexts, dev):
    # Expand any containerContext objects
    if 'containerContext' in container:
        context_name = container.get('containerContext')

        try:
            context = contexts[context_name]
        except KeyError:
            raise KubeConfigError('Missing containerContext: {0}'.format(
                context_name,
            ))

        # Merge in anything not explicitly defined on the container itself
        _merge_config(container, context)

    # Expand any dev keys from the dev config
    if dev and 'dev' in container:
        _merge_config(container, container.pop('dev'))

    # Apply any commandArguments
    if 'commandArguments' in container:
        # Duplicate the command here as it might be from a context so we don't
        # want to continuously append the arguments to the same base command.
        command = [cmd for cmd in container.pop('command')]
        command.extend(container.pop('commandArguments'))
        container['command'] = command

    return container
