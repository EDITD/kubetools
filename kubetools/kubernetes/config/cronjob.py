import shlex

from kubetools.kubernetes.api import check_if_cronjob_compatible
from kubetools.settings import get_settings

from .container import make_container_config
from .util import copy_and_update


def make_cronjob_config(
    config,
    cronjob_name,
    schedule,
    concurrency_policy,
    containers,
    labels=None,
    annotations=None,
    envvars=None,
):
    '''
    Builds a Kubernetes cronjob configuration dict.
    '''

    settings = get_settings()
    env = config.get('env', settings.DEFAULT_KUBE_ENV)
    apiVersion = 'batch/v1' if check_if_cronjob_compatible(env) else 'batch/v1beta1'

    labels = labels or {}
    annotations = annotations or {}

    # Build our container list
    kubernetes_containers = []
    for container_name, container in containers.items():
        # Figure out the command
        command = container['command']
        if isinstance(command, str):
            command = shlex.split(command)

        # Get/create description
        description = config.get('description', 'Run: {0}'.format(command))

        # Attach description to annotations
        annotations = copy_and_update(annotations, {
            'description': description,
        })

        kubernetes_containers.append(make_container_config(
            container_name, container,
            envvars=envvars,
            labels=labels,
            annotations=annotations,
        ))

    # The actual cronjob spec
    cronjob = {
        'apiVersion': apiVersion,
        'kind': 'CronJob',
        'metadata': {
            'name': cronjob_name,
            'labels': labels,
            'annotations': annotations,
        },
        'spec': {
            'schedule': schedule,
            'startingDeadlineSeconds': 10,
            'concurrencyPolicy': concurrency_policy,
            'jobTemplate': {
                'spec': {
                    'template': {
                        'metadata': {
                            'name': cronjob_name,
                            'labels': labels,
                            'annotations': annotations,
                        },
                        'spec': {
                            'restartPolicy': 'OnFailure',
                            'containers': kubernetes_containers,
                        },
                    },
                },
            },
        },
    }

    return cronjob
