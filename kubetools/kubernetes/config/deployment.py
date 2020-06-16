from .container import make_container_config
from .util import get_hash, make_dns_safe_name

DEPLOYMENT_REVISION_LIMIT = 5


def make_deployment_config(
    name, containers,
    replicas=1,
    labels=None,
    annotations=None,
    envvars=None,
    update_strategy=None,
):
    '''
    Builds a Kubernetes deployment configuration dict.
    '''

    labels = labels or {}
    annotations = annotations or {}

    # Build our container list
    kubernetes_containers = []
    for container_name, container in containers.items():
        kubernetes_containers.append(make_container_config(
            container_name, container,
            envvars=envvars,
            labels=labels,
            annotations=annotations,
        ))

    # The actual controller Kubernetes config
    controller = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {
            'name': make_dns_safe_name(name),
            'labels': labels,
            'annotations': annotations,
        },
        'spec': {
            'revisionHistoryLimit': DEPLOYMENT_REVISION_LIMIT,
            'selector': {
                'matchLabels': labels,
            },
            'replicas': replicas,
            'template': {
                'metadata': {
                    'labels': labels,
                },
                'spec': {
                    'containers': kubernetes_containers,
                },
            },
        },
    }

    if update_strategy:
        controller['spec']['strategy'] = update_strategy

    container_volumes = {}
    for container in containers.values():
        if 'volumes' in container:
            for volume in container['volumes']:
                name = get_hash(volume)
                container_volumes[name] = {
                    'name': name,
                    'hostPath': {
                        'path': volume.split(':')[0],
                    },
                }

    if container_volumes:  # kube does not like an empty list
        controller['spec']['template']['spec']['volumes'] = container_volumes.values()

    for container in containers:
        if 'volumes' in container:
            for volume in container['volumes']:
                controller['spec']['template'].setdefault('volumes', []).append({
                    'name': get_hash(volume),
                    'hostPath': {
                        'path': volume.split(':')[0],
                    },
                })

    return controller
