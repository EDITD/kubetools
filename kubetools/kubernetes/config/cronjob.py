import shlex

from .container import make_container_config
from .util import copy_and_update
from .volume import make_secret_volume_config


def make_cronjob_config(
    config,
    cronjob_name,
    cronjob_spec,
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

    node_selector_labels = cronjob_spec.get('nodeSelector', None)
    service_account_name = cronjob_spec.get('serviceAccountName', None)
    secrets = cronjob_spec.get('secrets', None)

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

    template_spec = {
        'restartPolicy': 'OnFailure',
        'containers': kubernetes_containers,
    }

    if node_selector_labels is not None:
        template_spec['nodeSelector'] = node_selector_labels

    if service_account_name is not None:
        template_spec['serviceAccountName'] = service_account_name

    if secrets is not None:
        kubernetes_volumes = []
        for secret_name, secret in secrets.items():
            kubernetes_volumes.append(make_secret_volume_config(
                secret_name, secret,
            ))
        template_spec['volumes'] = kubernetes_volumes

    # The actual cronjob spec
    cronjob = {
        'kind': 'CronJob',
        'metadata': {
            'name': cronjob_name,
            'labels': labels,
            'annotations': annotations,
        },
        'spec': {
            'schedule': cronjob_spec['schedule'],
            'startingDeadlineSeconds': 10,
            'concurrencyPolicy': cronjob_spec['concurrency_policy'],
            'jobTemplate': {
                'spec': {
                    'template': {
                        'metadata': {
                            'name': cronjob_name,
                            'labels': labels,
                            'annotations': annotations,
                        },
                        'spec': template_spec,
                    },
                },
            },
        },
    }
    batch_api_version = cronjob_spec.get('batch-api-version', None)
    if batch_api_version is not None:
        # Only set here if user has specified it in the config
        cronjob['apiVersion'] = batch_api_version

    successfulJobsHistoryLimit = cronjob_spec.get('successfulJobsHistoryLimit', None)
    if successfulJobsHistoryLimit is not None:
        cronjob['spec']['successfulJobsHistoryLimit'] = successfulJobsHistoryLimit
    failedJobsHistoryLimit = cronjob_spec.get('failedJobsHistoryLimit', None)
    if failedJobsHistoryLimit is not None:
        cronjob['spec']['failedJobsHistoryLimit'] = failedJobsHistoryLimit

    return cronjob
