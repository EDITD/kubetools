from .util import get_hash

# Keys to turn into environment variables
LABEL_ENVAR_KEYS = (
    'role',
    'app',
    'name',
    'commit',
    'project_name',
    'git_name',
    'manifest_name',
)
ANNOTATION_ENVAR_KEYS = ('version',)


def _make_probe_config(config):
    if 'httpGet' in config:
        # Ensure we have a HTTP port
        if 'port' not in config['httpGet']:
            config['httpGet']['port'] = 80

        # Ensure we have a HTTP path
        if 'path' not in config['httpGet']:
            config['httpGet']['path'] = '/'

    return config


def make_container_config(
    name, container,
    envvars=None, labels=None, annotations=None,
):
    '''
    Builds the common Kubernetes container config.
    '''

    envvars = envvars or {}
    labels = labels or {}
    annotations = annotations or {}

    image = container['image']

    container_data = {
        'name': name,

        # Always pull the image from the registry
        'imagePullPolicy': 'Always',
        'image': image,

        # Environment flag we use to determine if app is in Kube
        'env': [],
    }

    # Copy these keys as-is
    for key in ('livenessProbe', 'readinessProbe'):
        if key in container:
            container_data[key] = _make_probe_config(container.pop(key))

    # Probes is a shortcut for both ready and live probes
    if 'probes' in container:
        probes = container.pop('probes')
        container_data['livenessProbe'] = _make_probe_config(probes)
        container_data['readinessProbe'] = _make_probe_config(probes)

    # Attach any of these labels as envvars
    for key in LABEL_ENVAR_KEYS:
        if key in labels:
            env_key = 'KUBETOOLS_{0}'.format(key.upper())
            container_data['env'].append({
                'name': env_key,
                'value': labels[key],
            })

    # Attach any of these annotations as envvars
    for key in ANNOTATION_ENVAR_KEYS:
        if key in annotations:
            env_key = 'KUBETOOLS_{0}'.format(key.upper())
            container_data['env'].append({
                'name': env_key,
                'value': annotations[key],
            })

    # Attach environment from the config
    if 'environment' in container:
        for item in container.pop('environment'):
            k, v = item.split('=')

            container_data['env'].append({
                'name': k,
                'value': v,
            })

    # Attach extra envvars
    if envvars:
        container_data['env'].extend([
            {
                'name': key,
                'value': str(value),
            }
            for key, value in envvars.items()
        ])

    # Apply any container-config level ENVars
    if container.get('env'):
        container_data['env'].extend([
            {
                'name': key,
                'value': str(value),
            }
            for key, value in container['env'].items()
        ])

    if 'volumes' in container:
        container_data['volumeMounts'] = []
        for volume in container.pop('volumes'):
            container_data['volumeMounts'].append({
                'mountPath': volume.split(':')[1],
                'name': get_hash(volume),
            })

    # Finally, attach all remaining data
    container_data.update(container)

    return container_data
