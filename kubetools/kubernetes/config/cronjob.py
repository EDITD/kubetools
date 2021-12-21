from .container import make_container_config


def make_cronjob_config(
    cronjob_name,
    schedule,
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
        kubernetes_containers.append(make_container_config(
            container_name, container,
            envvars=envvars,
            labels=labels,
            annotations=annotations,
        ))

    # The actual cronjob spec
    cronjob = {
        'apiVersion': 'batch/v1',
        'startingDeadlineSeconds': 10,
        'suspend': 'false',
        'kind': 'CronJob',
        'metadata': {
            'name': cronjob_name,
            'labels': labels,
            'annotations': annotations,
        },
        'spec': {
            'schedule': schedule,
            'jobTemplate': {
                'spec': {
                    'template': {
                        'metadata': {
                            'labels': labels,
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
