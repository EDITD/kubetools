from .container import make_container_config
from .util import make_dns_safe_name


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
        'kind': 'CronJob',
        'metadata': {
            'name': make_dns_safe_name(cronjob_name)
        },
        'spec': {
            'schedule': schedule,
            'jobTemplate': {
                'spec': {
                    'template': {
                        'spec': {
                            'restartPolicy': 'OnFailure',
                            'containers': kubernetes_containers                         
                        },
                    },
                },
            },
        },
    }

    return cronjob