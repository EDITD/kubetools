import json
import os

import click

from kubetools.cli import cli_bootstrap
from kubetools.deploy.build import Build
from kubetools.deploy.commands.cleanup import (
    execute_cleanup,
    get_cleanup_objects,
    log_cleanup_changes,
)
from kubetools.deploy.commands.deploy import (
    execute_deploy,
    get_deploy_objects,
    log_deploy_changes,
)
from kubetools.deploy.commands.remove import (
    execute_remove,
    get_remove_objects,
    log_remove_changes,
)
from kubetools.deploy.commands.restart import (
    execute_restart,
    get_restart_objects,
    log_restart_changes,
)
from kubetools.kubernetes.api import get_object_name


def _dry_deploy_object_loop(object_type, objects):
    name_to_object = {
        get_object_name(obj): obj
        for obj in objects
    }

    while True:
        object_name = click.prompt(
            f'Print {object_type}?',
            type=click.Choice(name_to_object),
            default='exit',
        )

        if object_name == 'exit':
            break

        click.echo(json.dumps(name_to_object[object_name], indent=4))


def _dry_deploy_loop(build, services, deployments, jobs):
    for object_type, objects in (
        ('service', services),
        ('deployment', deployments),
        ('job', jobs),
    ):
        if objects:
            _dry_deploy_object_loop(object_type, objects)


@cli_bootstrap.command(help_priority=0)
@click.option(
    '--dry',
    is_flag=True,
    default=False,
    help='Instead of writing objects to Kubernetes, just print them and exit.',
)
@click.option(
    '--replicas',
    type=int,
    help='Default number of replicas for each app.',
)
@click.option(
    '--default-registry',
    help='Default registry for apps that do not specify.',
)
@click.option(
    '-y', '--yes',
    is_flag=True,
    default=False,
    help='Flag to auto-yes remove confirmation step.',
)
@click.argument('namespace')
@click.argument(
    'app_dirs',
    nargs=-1,
    type=click.Path(exists=True, file_okay=False),
)
@click.pass_context
def deploy(ctx, dry, replicas, default_registry, yes, namespace, app_dirs):
    '''
    Deploy an app, or apps, to Kubernetes.
    '''

    if not app_dirs:
        app_dirs = (os.getcwd(),)

    build = Build(
        env=ctx.meta['kube_context'],
        namespace=namespace,
    )

    services, deployments, jobs = get_deploy_objects(
        build, app_dirs,
        replicas=replicas,
        default_registry=default_registry,
    )

    if not any((services, deployments, jobs)):
        click.echo('Nothing to do!')
        return

    if dry:
        return _dry_deploy_loop(build, services, deployments, jobs)

    log_deploy_changes(
        build, services, deployments, jobs,
        message='Executing changes:' if yes else 'Proposed changes:',
        name_formatter=lambda name: click.style(name, bold=True),
    )

    if not yes:
        click.confirm(click.style((
            'Are you sure you wish to CREATE and UPDATE the above resources? '
            'This cannot be undone.'
        )), abort=True)
        click.echo()

    execute_deploy(
        build,
        services,
        deployments,
        jobs,
    )


@cli_bootstrap.command(help_priority=1)
@click.option(
    '-y', '--yes',
    is_flag=True,
    default=False,
    help='Flag to auto-yes remove confirmation step.',
)
@click.option(
    '-f', '--force',
    is_flag=True,
    default=False,
    help='Force kubetools to remove objects it does not own.',
)
@click.option(
    '--cleanup', 'do_cleanup',
    is_flag=True,
    default=False,
    help='Run a cleanup immediately after removal.',
)
@click.argument('namespace')
@click.argument('app_or_project_names', nargs=-1)
@click.pass_context
def remove(ctx, yes, force, do_cleanup, namespace, app_or_project_names):
    '''
    Removes one or more apps from a given namespace.
    '''

    build = Build(
        env=ctx.meta['kube_context'],
        namespace=namespace,
    )

    services_to_delete, deployments_to_delete, jobs_to_delete = (
        get_remove_objects(build, app_or_project_names, force=force)
    )

    if not any((services_to_delete, deployments_to_delete, jobs_to_delete)):
        click.echo('Nothing to do 👍!')
        return

    log_remove_changes(
        build, services_to_delete, deployments_to_delete, jobs_to_delete,
        message='Executing changes:' if yes else 'Proposed changes:',
        name_formatter=lambda name: click.style(name, bold=True),
    )

    if not yes:
        click.confirm(click.style(
            'Are you sure you wish to DELETE the above resources? This cannot be undone.',
        ), abort=True)
        click.echo()

    execute_remove(
        build,
        services_to_delete,
        deployments_to_delete,
        jobs_to_delete,
    )

    if do_cleanup:
        ctx.invoke(cleanup, yes=yes, namespace=namespace)


@cli_bootstrap.command(help_priority=2)
@click.option(
    '-y', '--yes',
    is_flag=True,
    default=False,
    help='Flag to auto-yes remove confirmation step.',
)
@click.argument('namespace')
@click.pass_context
def cleanup(ctx, yes, namespace):
    '''
    Cleans up a namespace by removing orphaned objects.
    '''

    build = Build(
        env=ctx.meta['kube_context'],
        namespace=namespace,
    )

    replica_sets_to_delete, pods_to_delete = get_cleanup_objects(build)

    if not any((replica_sets_to_delete, pods_to_delete)):
        click.echo('Nothing to do 👍!')
        return

    log_cleanup_changes(
        build, replica_sets_to_delete, pods_to_delete,
        message='Executing changes:' if yes else 'Proposed changes:',
        name_formatter=lambda name: click.style(name, bold=True),
    )

    if not yes:
        click.confirm(click.style(
            'Are you sure you wish to DELETE the above resources? This cannot be undone.',
        ), abort=True)
        click.echo()

    execute_cleanup(
        build,
        replica_sets_to_delete,
        pods_to_delete,
    )


@cli_bootstrap.command()
@click.option(
    '-y', '--yes',
    is_flag=True,
    default=False,
    help='Flag to auto-yes remove confirmation step.',
)
@click.argument('namespace')
@click.argument('app_or_project_names', nargs=-1)
@click.pass_context
def restart(ctx, yes, namespace, app_or_project_names):
    '''
    Restarts one or more apps in a given namespace.
    '''

    build = Build(
        env=ctx.meta['kube_context'],
        namespace=namespace,
    )

    deployments_and_pods_to_delete = get_restart_objects(build, app_or_project_names)

    if not deployments_and_pods_to_delete:
        click.echo('Nothing to do 👍!')
        return

    log_restart_changes(
        build, deployments_and_pods_to_delete,
        message='Executing changes:' if yes else 'Proposed changes:',
        name_formatter=lambda name: click.style(name, bold=True),
    )

    if not yes:
        click.confirm(click.style(
            'Are you sure you wish to DELETE the above resources? This cannot be undone.',
        ), abort=True)
        click.echo()

    execute_restart(
        build,
        deployments_and_pods_to_delete,
    )
