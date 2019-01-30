# Kubetools Client
# File: kubetools/cli/__init__.py
# Desc: helpers for the Kubetools command line interface

import click
import six

from kubetools_client.cli import cli_bootstrap
from kubetools_client.cli.wait import wait_build, wait_job
from kubetools_client.exceptions import KubeCLIError
from kubetools_client.log import logger


def _get_apps_in_namespace(client, namespace):
    return client.list_apps_by_namespace().get(namespace, {})


def _parse_envars(envars):
    return dict(
        envar.split('=', 1)
        for envar in envars
    )


def _parse_build_options(apps, envars=None):
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

        if envars:
            app_to_build['envars'] = _parse_envars(envars)

        apps_to_build.append(app_to_build)

    logger.debug('Converted CLI app spec: {0} -> {1}'.format(
        apps, apps_to_build,
    ))

    return apps_to_build


def _generate_build_deploy(
    action, client, func,
    build_options=None,
    envars=None,
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

    apps = _parse_build_options(build_options, envars=envars)

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


@cli_bootstrap.command()
@click.argument('build_options', nargs=-1, required=True)
@click.pass_obj
def build(client, build_options):
    '''
    Builds all containers needed for an app.
    '''

    return _generate_build_deploy(
        'Building', client, client.create_build, build_options,
    )


@cli_bootstrap.command()
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
        envars=envar,
    )


@cli_bootstrap.command()
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


@cli_bootstrap.command()
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


@cli_bootstrap.command()
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


@cli_bootstrap.command()
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


@cli_bootstrap.command()
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

    # Parse/inject any envars
    if envar:
        job_spec['envars'] = _parse_envars(envar)

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
