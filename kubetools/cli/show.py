import click

from tabulate import tabulate

from kubetools.constants import (
    GIT_BRANCH_ANNOTATION_KEY,
    GIT_COMMIT_ANNOTATION_KEY,
    GIT_TAG_ANNOTATION_KEY,
    NAME_LABEL_KEY,
    PROJECT_NAME_LABEL_KEY,
    ROLE_LABEL_KEY,
)
from kubetools.kubernetes.api import (
    get_object_annotations_dict,
    get_object_labels_dict,
    get_object_name,
    is_kubetools_object,
    list_cronjobs,
    list_deployments,
    list_jobs,
    list_replica_sets,
    list_services,
)

from . import cli_bootstrap


def _get_service_meta(service):
    meta_items = []
    for port in service.spec.ports:
        meta_items.append(f'port={port.port}, nodePort={port.node_port}')
    return ''.join(meta_items)


def _print_items(items, header_to_getter=None):
    header_to_getter = header_to_getter or {}

    headers = ['Name', 'Role', 'Project']
    headers.extend(header_to_getter.keys())
    headers = [click.style(header, bold=True) for header in headers]

    rows = []
    for item in items:
        labels = get_object_labels_dict(item)

        row = [
            get_object_name(item),
            labels.get(ROLE_LABEL_KEY),
        ]

        if not is_kubetools_object(item):
            row.append(click.style('NOT MANAGED BY KUBETOOLS', 'yellow'))
        else:
            row.append(labels.get(PROJECT_NAME_LABEL_KEY, 'unknown'))

        for getter in header_to_getter.values():
            row.append(getter(item))

        rows.append(row)

    click.echo(tabulate(rows, headers=headers, tablefmt='simple'))


def _get_node_ports(item):
    node_ports = []
    for port in item.spec.ports:
        if port.node_port:
            node_ports.append(f'{port.port}:{port.node_port}')
        else:
            node_ports.append(f'{port.port}')

    return ', '.join(node_ports)


def _get_ready_status(item):
    return f'{item.status.ready_replicas or 0}/{item.status.replicas}'


def _get_version_info(item):
    annotations = get_object_annotations_dict(item)
    bits = []
    for name, key in (
        ('branch', GIT_BRANCH_ANNOTATION_KEY),
        ('tag', GIT_TAG_ANNOTATION_KEY),
        ('commit', GIT_COMMIT_ANNOTATION_KEY),
    ):
        data = annotations.get(key)
        if data:
            bits.append(f'{name}={data}')

    return ', '.join(bits)


def _get_completion_status(item):
    return f'{item.status.succeeded}/{item.spec.completions}'


def _get_command(item):
    return get_object_annotations_dict(item).get('description')


@cli_bootstrap.command(help_priority=3)
@click.argument('namespace')
@click.argument('app', required=False)
@click.pass_context
def show(ctx, namespace, app):
    '''
    Show running apps in a given namespace.
    '''

    exists = False

    env = ctx.meta['kube_context']

    if app:
        click.echo(f'--> Filtering by app={app}')

    services = list_services(env, namespace)

    if services:
        exists = True

        if app:
            services = [s for s in services if get_object_name(s) == app]

        click.echo(f'--> {len(services)} Services')
        _print_items(services, {
            'Port(:nodePort)': _get_node_ports,
        })
        click.echo()

    deployments = list_deployments(env, namespace)

    if deployments:
        exists = True

        if app:
            deployments = [d for d in deployments if get_object_name(d) == app]

        click.echo(f'--> {len(deployments)} Deployments')

        _print_items(deployments, {
            'Ready': _get_ready_status,
            'Version': _get_version_info,
        })
        click.echo()

    if app:
        replica_sets = list_replica_sets(env, namespace)
        replica_sets = [
            r for r in replica_sets
            if r.metadata.labels.get(NAME_LABEL_KEY) == app
        ]

        click.echo(f'--> {len(replica_sets)} Replica sets')
        _print_items(replica_sets, {
            'Ready': _get_ready_status,
            'Version': _get_version_info,
        })
        click.echo()
    else:
        cronjobs = list_cronjobs(env, namespace)

        if cronjobs:
            exists = True

            click.echo(f'--> {len(cronjobs)} Cronjobs')

            _print_items(cronjobs, {
                'Ready': _get_cronjob_status,
                'Version': _get_version_info,
            })
            click.echo()

        jobs = []
        jobs_cronjobs = []
        job_list = list_jobs(env, namespace)
        if job_list:
            for job in job_list:
                labels = get_object_labels_dict(job)
                if labels.get(ROLE_LABEL_KEY) == 'job':
                    jobs.append(job)
                elif labels.get(ROLE_LABEL_KEY) == 'cronjob':
                    jobs_cronjobs.append(job)

            if jobs_cronjobs:
                exists = True
                click.echo(f'--> {len(jobs_cronjobs)} Jobs created by Cronjobs')

                _print_items(jobs_cronjobs, {
                    'Completions': _get_completion_status,
                    'Command': _get_command,
                })
                click.echo()

            if jobs:
                exists = True
                click.echo(f'--> {len(jobs)} Jobs')
                _print_items(jobs, {
                    'Completions': _get_completion_status,
                    'Command': _get_command,
                })
                click.echo()

    if not exists:
        click.echo('Nothing to be found here 👀!')


def _get_cronjob_status(item):
    if item.status.active is not None:
        # Job is currently running (implies successfully started)
        return "?/1"
    elif item.status.last_successful_time is not None:
        # Job has been successful (implies successfully started)
        return "1/1"
    elif item.status.last_schedule_time is not None:
        # Job has been scheduled
        return "0/1"
    else:
        # Job has never been scheduled (error in CronJob?)
        return "0/0"
