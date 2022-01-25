import shlex

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
        'apiVersion': 'batch/v1',
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
