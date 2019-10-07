import six

from .container import make_container_config
from .util import get_hash, make_dns_safe_name

DEPLOYMENT_REVISION_LIMIT = 5


def make_deployment_config(
    name, containers,
    replicas=1,
    kube_env=None,
    namespace=None,
    labels=None,
    annotations=None,
    version=None,
    envars=None,
):
    '''
    Builds a Kubernetes deployment configuration dict.
    '''

    labels = labels or {}
    annotations = annotations or {}

    # Build our container list
    kubernetes_containers = []
    for container_name, container in six.iteritems(containers):
        if (
            # No env specified or env matching config envs
            not kube_env or kube_env in container.get('envs', [kube_env])
        ) and (
            # No namespace specified or namespace matching namespace envs
            not namespace or namespace in container.get('namespaces', [namespace])
        ):
            kubernetes_containers.append(make_container_config(
                container_name, container,
                kube_env=kube_env, namespace=namespace,
                version=version, envars=envars,
                labels=labels, annotations=annotations,
            ))

    # The actual controller Kubernetes config
    controller = {
        'apiVersion': 'apps/v1beta1',
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
