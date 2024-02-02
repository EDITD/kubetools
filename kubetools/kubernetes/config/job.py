import shlex
from uuid import uuid4

from .container import make_container_config
from .util import copy_and_update
from .volume import make_secret_volume_config


def make_job_config(
    config,
    app_name=None,
    labels=None,
    annotations=None,
    envvars=None,
    job_name=None,
    container_name="upgrade",
    node_selector_labels=None,
    service_account_name=None,
    secrets=None,
):
    '''
    Builds a Kubernetes job configuration dict.
    '''

    # We want a copy of these because we'll modify them below
    labels = labels or {}
    envvars = envvars or {}
    annotations = annotations or {}

    # Generate name
    job_id = str(uuid4())
    if job_name is None:
        job_name = job_id

    # Attach the ID to labels
    labels = copy_and_update(labels, {
        'job-id': job_id,
    })

    # Figure out the command
    command = config['command']

    if isinstance(command, str):
        command = shlex.split(command)

    # Get/create description
    description = config.get('description', 'Run: {0}'.format(command))

    # Attach description to annotations
    annotations = copy_and_update(annotations, {
        'description': description,
    })

    # Update global envvars with job specific ones
    envvars = copy_and_update(
        envvars,
        config.get('envars'),  # legacy support TODO: remove!
        config.get('envvars'),
        {'KUBE_JOB_ID': job_id},
    )

    # Make our container
    container = make_container_config(
        job_id,
        {
            'name': container_name,
            'command': command,
            'image': config['image'],
            'chdir': config.get('chdir', '/'),
            'resources': config.get('resources', {}),
        },
        envvars=envvars,
        labels=labels,
        annotations=annotations,
        secrets=secrets,
    )

    # Completions default to 1, same as Kubernetes
    completions = config.get('completions', 1)
    # Parallelism defaults to completions, also as Kubernetes
    parallelism = config.get('parallelism', completions)

    template_spec = {
        'restartPolicy': 'Never',
        'containers': [container],
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

    job_config = {
        # Normal Kubernetes job config
        'apiVersion': 'batch/v1',
        'kind': 'Job',
        'metadata': {
            'name': job_name,
            'labels': labels,
            'annotations': annotations,
        },
        'spec': {
            'completions': completions,
            'parallelism': parallelism,
            'selector': labels,
            'template': {
                'metadata': {
                    'labels': labels,
                },
                'spec': template_spec,
            },
        },
    }

    if 'ttl_seconds_after_finished' in config:
        job_config['spec']['ttlSecondsAfterFinished'] = config.get('ttl_seconds_after_finished')

    return job_config
