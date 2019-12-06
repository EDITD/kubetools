import sys

import click
import six

from kubetools_client import KubeClient
from kubetools_client.cli import cli_bootstrap
from kubetools_client.exceptions import KubeCLIError
from kubetools_client.log import logger
from kubetools_client.settings import get_settings

from .server_util import wait_with_spinner


def _get_apps_in_namespace(client, namespace):
    return client.list_apps_by_namespace().get(namespace, {})


def _parse_envvars(envvars):
    return dict(
        envar.split('=', 1)
        for envar in envvars
    )


def _parse_build_options(apps, envvars=None):
    apps_to_build = []

    for app in apps:
        replicas = version = None

        if '*' in app:
            app, replicas = app.split('*')
            replicas = int(replicas)

        if '=' in app:
            app, version = app.split('=')

        app_to_build = {
            'app': app,
        }

        if replicas:
            app_to_build['replicas'] = replicas

        if version:
            app_to_build['version'] = version

        if envvars:
            app_to_build['envvars'] = _parse_envvars(envvars)

        apps_to_build.append(app_to_build)

    logger.debug('Converted CLI app spec: {0} -> {1}'.format(
        apps, apps_to_build,
    ))

    return apps_to_build


def _generate_build_deploy(
    action, client, func,
    build_options=None,
    envvars=None,
    **kwargs
):
    '''
    CLI helper for generating builds/deploys from command line input and then waiting on
    Kubetools to complete the build.
    '''

    build_options = build_options or []
    namespace = kwargs.get('namespace')

    click.echo('### {0}: {1}{2}'.format(
        action,
        '{0}/'.format(namespace) if namespace else '',
        click.style((
            ', '.join(build_options)
            if build_options
            else 'all'
        ), bold=True),
    ))
    click.echo()

    apps = _parse_build_options(build_options, envvars=envvars)

    # Cleanup only provides namespace
    if func == client.create_cleanup:
        build_hash = func(kwargs.pop('namespace'))

    # Upgrade/remove require namespace first
    elif func in (client.create_upgrade, client.create_remove, client.create_restart):
        build_hash = func(kwargs.pop('namespace'), apps)

    # Deploy/build doesn't need a namespace
    else:
        build_hash = func(apps, **kwargs)

    # Now wait for the build to complete
    click.echo('--> {0} queued, hash: {1}'.format(action, click.style(build_hash, bold=True)))
    wait_build(client, build_hash)


def _check_existing_apps(client, namespace, action):
    # Build full app spec based on the existing services
    existing_apps = _get_apps_in_namespace(client, namespace)

    if not existing_apps:
        raise KubeCLIError('No apps under namespace {0}, nothing to {1}'.format(
            namespace, action,
        ))


def wait_job(client, namespace, job_id):
    def check_job_status(previous_status):
        namespace_jobs = client.list_jobs_by_namespace(namespace=namespace)
        job = namespace_jobs[namespace][job_id]

        if (
            # Job completed the number of times we want?
            job['succeeded'] == job['completions']
            # Job has failed over X times?
            or job['failed'] >= job['backoffLimit']
        ):
            return

        return job['annotations'].get('description', 'Running job')

    wait_with_spinner(check_job_status)

    # Get the job again
    namespace_jobs = client.list_jobs_by_namespace(namespace=namespace)
    job = namespace_jobs[namespace][job_id]
    status = job['succeeded'] == job['completions']

    if status:
        click.echo('<-- Job complete, final status = {0}'.format(
            click.style('SUCCESS', 'green'),
        ))

    else:
        click.echo('<-- Job complete, final status = {0}'.format(
            click.style('ERROR', 'red'),
        ))

    if not status:
        sys.exit(1)


def wait_build(client, build_hash):
    '''
    CLI helper that waits for a build to complete while displaying a little spinner.
    '''

    def check_build_status(previous_status):
        build_data = client.get_build(build_hash)

        # If we're complete, just return nothing
        if build_data['status'] not in ('PENDING', 'RUNNING'):
            return

        status_text = build_data['status']
        if build_data['status_detail']:
            status_text = '{0}/{1}'.format(status_text, build_data['status_detail'])

        return status_text

    wait_with_spinner(check_build_status)

    # Get the build date
    build_data = client.get_build(build_hash)
    status = build_data['status']

    # We did it!
    if status == 'SUCCESS':
        click.echo('--> Namespace: {0}'.format(click.style(
            build_data['namespace'], bold=True,
        )))

        domains = build_data.get('domains')
        if domains:
            for app, domain in domains.items():
                click.echo('--> App: {0} should now be available @ {1}'.format(
                    app, click.style(domain, bold=True),
                ))

    elif status == 'ABORTED':
        click.echo('--> {0}'.format(
            click.style(
                'Aborted at stage: {0}'.format(build_data['status_detail']),
                'yellow',
            ),
        ))

    # Status should be ERROR, but any non-success here is a fail
    else:
        click.echo('--> {0}'.format(
            click.style(
                'Error at stage: {0}'.format(build_data['status_detail']),
                'red',
            ),
        ))
        click.echo()
        click.echo('--------ERROR START--------')
        click.echo(click.style(build_data.get('error', 'Unknown error'), 'yellow'))
        click.echo('---------ERROR END---------')

    if status == 'SUCCESS':
        formatted_status = click.style('SUCCESS', 'green')
    elif status == 'ABORTED':
        formatted_status = click.style('ABORTED', 'yellow')
    else:
        formatted_status = click.style('ERROR', 'red')

    click.echo('<-- Build complete, final status = {0}'.format(formatted_status))

    if status == 'ABORTED':
        sys.exit(1)

    elif status != 'SUCCESS':
        sys.exit(2)


@cli_bootstrap.group(help_priority=2)
@click.option(
    '-s', '--server',
    envvar='KUBETOOLS_HOST',
)
@click.option(
    '-p', '--port',
    type=int,
    envvar='KUBETOOLS_PORT',
)
@click.option('kube_env', '--env', '--kube-env')
@click.pass_context
def server(ctx, server=None, port=None, kube_env=None):
    '''
    Trigger builds on a Kubetools server.
    '''

    settings = get_settings()

    # CLI options > settings
    host = server or settings.KUBETOOLS_HOST
    port = port or settings.KUBETOOLS_PORT
    kube_env = kube_env or settings.DEFAULT_KUBE_ENV

    # Setup the client
    ctx.obj = KubeClient(host=host, port=port, kube_env=kube_env)


@server.command()
@click.argument('namespace')
@click.argument('job_id')
@click.pass_obj
def abort_job(client, namespace, job_id):
    if client.abort_job(namespace, job_id):
        click.echo('--> Job aborted: {0}/{1}'.format(
            namespace,
            click.style(job_id, bold=True),
        ))
    else:
        click.echo(click.style('Failed to abort job!', 'red'))


@server.command()
@click.argument('namespace')
@click.argument('job_id')
@click.pass_obj
def delete_job(client, namespace, job_id):
    if client.delete_job(namespace, job_id):
        click.echo('--> Job deleted: {0}/{1}'.format(
            namespace,
            click.style(job_id, bold=True),
        ))
    else:
        click.echo(click.style('Failed to delete job!', 'red'))


@server.command()
@click.argument('build_hash')
@click.pass_obj
def wait(client, build_hash):
    '''
    Wait for a Kubetools build.
    '''

    click.echo('### Watching build: {0}'.format(
        click.style(build_hash, bold=True),
    ))
    wait_build(client, build_hash)


@server.command()
@click.argument('build_options', nargs=-1, required=True)
@click.pass_obj
def build(client, build_options):
    '''
    Builds all containers needed for an app.
    '''

    return _generate_build_deploy(
        'Building', client, client.create_build, build_options,
    )


@server.command()
@click.argument('namespace')
@click.argument('deploy_options', nargs=-1, required=True)
@click.option(
    '-e', '--envar',
    multiple=True,
    help='Envars to pass into the app containers.',
)
@click.pass_obj
def deploy(client, deploy_options, namespace=None, envar=None):
    '''
    Deploy apps into a new or existing namespace.
    '''

    return _generate_build_deploy(
        'Deploying', client, client.create_deploy,
        build_options=deploy_options,
        namespace=namespace,
        envvars=envar,
    )


@server.command()
@click.argument('namespace')
@click.argument('upgrade_options', nargs=-1)
@click.pass_obj
def upgrade(client, namespace, upgrade_options):
    '''
    Upgrade apps in a namespace.
    '''

    _check_existing_apps(client, namespace, 'upgrade')

    return _generate_build_deploy(
        'Upgrading', client, client.create_upgrade,
        build_options=upgrade_options,
        namespace=namespace,
    )


@server.command()
@click.argument('namespace')
@click.argument('apps_to_remove', nargs=-1)
@click.pass_obj
def remove(client, namespace, apps_to_remove):
    '''
    Remove apps from a namespace.
    '''

    _check_existing_apps(client, namespace, 'remove')

    return _generate_build_deploy(
        'Removing', client, client.create_remove,
        build_options=apps_to_remove,
        namespace=namespace,
    )


@server.command()
@click.argument('namespace')
@click.argument('apps_to_restart', nargs=-1)
@click.pass_obj
def restart(client, namespace, apps_to_restart):
    '''
    Restart apps in a namespace.
    '''

    _check_existing_apps(client, namespace, 'restart')

    return _generate_build_deploy(
        'Restarting', client, client.create_restart,
        build_options=apps_to_restart,
        namespace=namespace,
    )


@server.command()
@click.argument('namespace')
@click.pass_obj
def cleanup(client, namespace):
    '''
    Cleanup a namespace.
    '''

    _check_existing_apps(client, namespace, 'cleanup')

    return _generate_build_deploy(
        'Cleaning', client, client.create_cleanup,
        namespace=namespace,
    )


@server.command()
@click.argument('namespace')
@click.argument('app')
@click.argument('command')
@click.option(
    '-e', '--envar',
    multiple=True,
    help='Envars to pass into the app containers.',
)
@click.option(
    '--chdir',
    help='Directory inside the container to execute the command.',
)
@click.pass_obj
def run(
    client, namespace, app, command,
    envar=None, chdir=None,
):
    '''
    Run commands for an app in a given namespace.
    '''

    click.echo('### Running {0} on {1}'.format(
        click.style(command, bold=True),
        click.style(app, bold=True),
    ))
    click.echo()

    apps = _parse_build_options([app])
    job_spec = {
        'command': command,
    }

    if chdir:
        job_spec['chdir'] = chdir

    # Parse/inject any envvars
    if envar:
        job_spec['envvars'] = _parse_envvars(envar)

    # Splice in our command for each app as a job
    for app in apps:
        app['job'] = job_spec

    build_hash = client.create_run(apps, namespace=namespace)

    # Now wait for the *build* to complete
    click.echo('--> Waiting for build: {0}'.format(click.style(build_hash, bold=True)))
    wait_build(client, build_hash)

    # Now fetch the jobs in the namespace and find the job created by this build
    namespace_jobs = client.list_jobs_by_namespace(namespace=namespace)
    jobs = namespace_jobs[namespace]

    job_id = None

    for id_, data in six.iteritems(jobs):
        if data['annotations'].get('kubetools/build_hash') == build_hash:
            job_id = id_
            break

    click.echo()
    click.echo('--> Waiting for job: {0}'.format(click.style(job_id, bold=True)))
    wait_job(client, namespace, job_id)
