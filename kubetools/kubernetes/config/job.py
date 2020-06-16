import shlex
from uuid import uuid4

from .container import make_container_config
from .util import copy_and_update


def make_job_config(
    config,
    app_name=None,
    labels=None,
    annotations=None,
    envvars=None,
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
    copy_and_update(
        envvars,
        config.get('envars'),  # legacy support TODO: remove!
        config.get('envvars'),
    )

    # Make our container
    container = make_container_config(
        job_id,
        {
            'name': 'upgrade',
            'command': command,
            'image': config['image'],
            'chdir': config.get('chdir', '/'),
        },
        envvars=envvars,
        labels=labels,
        annotations=annotations,
    )

    # Completions default to 1, same as Kubernetes
    completions = config.get('completions', 1)
    # Parallelism defaults to completions, also as Kubernetes
    parallelism = config.get('parallelism', completions)

    return {
        # Normal Kubernetes job config
        'apiVersion': 'batch/v1',
        'kind': 'Job',
        'metadata': {
            'name': job_id,
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
                'spec': {
                    'restartPolicy': 'Never',
                    'containers': [container],
                },
            },
        },
    }
