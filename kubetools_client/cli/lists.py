# Kubetools Client
# File: kubetools/cli/lists.py
# Desc:

import click
import six

from six.moves import xrange

from kubetools_client.cli import cli_bootstrap


@cli_bootstrap.group()
def list():
    '''
    List Kubetools things.
    '''


@list.command()
@click.pass_obj
def manifests(client):
    '''
    List manifests on the Kubetools server.
    '''

    click.echo('### Manifests')
    click.echo()

    for manifest in client.list_manifests():
        click.echo('--> {0}'.format(click.style(manifest, bold=True)))

    click.echo()


@list.command()
@click.pass_obj
def envs(client):
    '''
    List available Kubernetes environments.
    '''

    click.echo('### Environments')
    click.echo()

    for name, environment in six.iteritems(client.list_environments()):
        click.echo('--> {0}'.format(click.style(name, bold=True)))
        for key in ('host', 'proxy', 'kubernetes', 'registry'):
            click.echo('    {0}: {1}'.format(
                key.title(),
                click.style(environment[key], bold=True),
            ))

        click.echo()


@list.command()
@click.option('--status', default=None, help='Filter builds by status.')
@click.option('--limit', default=20, help='Number of builds to fetch.')
@click.option('--offset', default=0, help='Offset the builds to fetch.')
@click.pass_obj
def builds(client, status=None, limit=20, offset=0):
    '''
    List Kubetools builds.
    '''

    click.echo('### Builds')
    click.echo()

    builds = client.list_builds(
        status=status,
        limit=limit,
        offset=offset,
    )

    if not builds:
        click.echo('--> No builds found!')
        return

    # The API list builds most recent first, but in a CLI we actually want the most recent
    # at the bottom of the output.
    builds = sorted(builds, reverse=True)

    status_to_color = {
        'SUCCESS': 'green',
        'ERROR': 'red',
        'RUNNING': 'blue',
    }

    for build in builds:
        status = build['status']

        if status in status_to_color:
            status = click.style(status, status_to_color[status])

        click.echo('--> hash={0} started={1}, status={2}'.format(
            click.style(build['hash'], bold=True),
            build['date_started'], status,
        ))

    click.echo()


@list.command()
@click.argument('namespace', required=False)
@click.option('--print-pods', default=False, is_flag=True, help='Show pod names.')
@click.pass_obj
def jobs(client, namespace=None, print_pods=False):
    '''
    List jobs and namespaces in Kubernetes.
    '''

    click.echo('### Jobs')
    click.echo()

    namespace_jobs = client.list_jobs_by_namespace(namespace=namespace)

    for namespace, jobs in six.iteritems(namespace_jobs):
        click.echo('--> {0}'.format(click.style(namespace, bold=True)))
        click.echo('    Jobs:')

        for job_id, job in six.iteritems(jobs):
            status = '{0}/{1} completed'.format(
                job['succeeded'],
                job['completions'],
            )

            if job['succeeded'] == job['completions']:
                status = click.style(status, 'green')

            click.echo('    - {0}, {1}, {2} pods ({3})'.format(
                click.style(job['annotations'].get('description', 'Unknown'), bold=True),
                status,
                len(job['pods']),
                job_id,
            ))

            if print_pods:
                if job.get('pods'):
                    click.echo('      pods: {0}'.format(', '.join(
                        pod['name'] for pod in job['pods']
                    )))

        click.echo()


@list.command()
@click.argument('namespace', required=False)
@click.option(
    'print_urls', '--urls',
    default=False, is_flag=True,
    help='Show app URLs.',
)
@click.option(
    'print_deployments', '--deployments',
    default=False, is_flag=True,
    help='Show Kubernetes deployments.',
)
@click.option(
    'print_replicasets', '--replicasets',
    default=False, is_flag=True,
    help='Show Kubernetes replicasets.',
)
@click.option(
    'print_pods', '--pods',
    default=False, is_flag=True,
    help='Show Kubernetes pods.',
)
@click.option(
    '--kubernetes-objects',
    default=False, is_flag=True,
    help='Shortcut for --deployments --replicasets --pods',
)
@click.pass_obj
def apps(
    client, namespace,
    print_urls=False,
    print_deployments=False,
    print_replicasets=False,
    print_pods=False,
    kubernetes_objects=False,
):
    '''
    List apps and namespaces in Kubernetes.
    '''

    # Apply the --kubernetes-objects shortcut
    if kubernetes_objects:
        print_deployments = True
        print_replicasets = True
        print_pods = True

    click.echo('### Apps')
    click.echo()

    # Get the aps
    namespace_apps = client.list_apps_by_namespace(
        namespace=namespace,
        include_replicasets=print_replicasets,
        include_pods=print_pods,
    )

    # Figure out the longest service name for printing
    longest_name = 0
    name_lengths = []

    for apps in namespace_apps.values():
        if apps:
            name_lengths.extend(
                [len(name) for name in apps],
            )

    if name_lengths:
        longest_name = max(name_lengths) + 5

    # Now actually loop & click.echo(the output)
    for namespace, apps in six.iteritems(namespace_apps):
        click.echo('--> Namespace: {0}'.format(click.style(namespace, bold=True)))

        if apps:
            click.echo('    Apps:')

            for name, service in six.iteritems(apps):
                available_replicas = service['replicas']['available']
                desired_replicas = service['replicas']['desired']

                pod_status = '{0}/{1} running'.format(
                    available_replicas, desired_replicas,
                )
                version = service['annotations'].get('version')
                commit = service['selector'].get('commit')

                # Both version & commit (usual)
                if version and commit:
                    version = '{0} ({1})'.format(version, commit)

                # No version but commit
                elif not version and commit:
                    version = commit

                # No version, no commit
                elif not version:
                    version = 'unknown'

                if available_replicas == desired_replicas:
                    pod_status = click.style(pod_status, 'green')
                elif available_replicas > 0:
                    pod_status = click.style(pod_status, 'yellow')
                else:
                    pod_status = click.style(pod_status, 'red')

                click.echo('    - {0}{1}{2} @ {3}'.format(
                    click.style(name, bold=True),
                    ''.join(
                        ' ' for _ in xrange(
                            0, (longest_name - len(name)),
                        )
                    ),
                    pod_status, version,
                ))

                if print_urls and 'url' in service:
                    click.echo('      Link: {0}'.format(
                        click.style(service['url'][7:], bold=True),
                    ))

                kube_objects = service['kubernetes_objects']

                if print_deployments and 'deployment' in kube_objects:
                    click.echo('      deployment: {0}'.format(
                        click.style(kube_objects['deployment']['name']),
                    ))

                if print_replicasets and 'replicaset' in kube_objects:
                    click.echo('      Replicaset: {0}'.format(
                        click.style(kube_objects['replicaset']['name']),
                    ))

                if print_pods and 'pods' in kube_objects:
                    click.echo('      Pods:')
                    for pod in kube_objects['pods']:
                        click.echo('      - {0}'.format(pod['name']))

        click.echo()
