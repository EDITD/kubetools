import shlex

from .container import make_container_config
from .util import copy_and_update
from .volume import make_secret_volume_config


def make_cronjob_config(
    config,
    cronjob_name,
    schedule,
    batch_api_version,
    concurrency_policy,
    containers,
    labels=None,
    annotations=None,
    envvars=None,
    service_account_name=None,
    secrets=None,
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
            secrets=secrets,
        ))

    kubernetes_spec = {}
    if service_account_name is not None and secrets is not None:
        kubernetes_volumes = []
        for secret_name, secret in secrets.items():
            kubernetes_volumes.append(make_secret_volume_config(
                secret_name, secret,
            ))
        kubernetes_spec['serviceAccountName'] = service_account_name
        kubernetes_spec['volumes'] = kubernetes_volumes

    kubernetes_spec['restartPolicy'] = 'OnFailure'
    kubernetes_spec['containers'] = kubernetes_containers

    # The actual cronjob spec
    cronjob = {
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
                        'spec': kubernetes_spec,
                    },
                },
            },
        },
    }
    if batch_api_version:
        # Only set here if user has specified it in the config
        cronjob['apiVersion'] = batch_api_version

    return cronjob
