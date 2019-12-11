import json
import os

import click

from kubetools_client.cli import cli_bootstrap
from kubetools_client.config import load_kubetools_config
from kubetools_client.deploy import (
    execute_cleanup,
    execute_deploy,
    execute_remove,
    execute_restart,
    get_cleanup_objects,
    log_cleanup_changes,
    log_deploy_changes,
    log_remove_changes,
)
from kubetools_client.deploy.build import Build
from kubetools_client.deploy.image import ensure_docker_images
from kubetools_client.deploy.kubernetes.api import (
    get_object_name,
    list_deployments,
    list_jobs,
    list_services,
)
from kubetools_client.deploy.kubernetes.config import generate_kubernetes_configs_for_project
from kubetools_client.deploy.util import run_shell_command
from kubetools_client.exceptions import KubeBuildError


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


def _get_git_info(app_dir):
    git_annotations = {}

    commit_hash = run_shell_command(
        'git', 'rev-parse', '--short=7', 'HEAD',
        cwd=app_dir,
    ).strip().decode()
    git_annotations['kubetools/git_commit'] = commit_hash

    branch_name = run_shell_command(
        'git', 'rev-parse', '--abbrev-ref', 'HEAD',
        cwd=app_dir,
    ).strip().decode()

    if branch_name != 'HEAD':
        git_annotations['kubetools/git_branch'] = branch_name

    try:
        git_annotations['kubetools/git_tag'] = run_shell_command(
            'git', 'tag', '--points-at', commit_hash,
            cwd=app_dir,
        ).strip().decode()
    except KubeBuildError:
        pass

    return commit_hash, git_annotations


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
    default=1,
    help='Default number of replicas for each app.',
)
@click.option(
    '--registry',
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
def deploy(ctx, dry, replicas, registry, yes, namespace, app_dirs):
    '''
    Deploy an app, or apps, to Kubernetes.
    '''

    if not app_dirs:
        app_dirs = (os.getcwd(),)

    build = Build(
        env=ctx.meta['kube_context'],
        namespace=namespace,
    )

    all_services = []
    all_deployments = []
    all_jobs = []

    for app_dir in app_dirs:
        envvars = {
            'KUBE_ENV': build.env,
            'KUBE_NAMESPACE': build.namespace,
        }

        annotations = {
            'kubetools/env': build.env,
            'kubetools/namespace': build.namespace,
        }

        if os.path.exists(os.path.join(app_dir, '.git')):
            commit_hash, git_annotations = _get_git_info(app_dir)
            annotations.update(git_annotations)
        else:
            raise click.BadParameter(f'{app_dir} is not a valid git repository!')

        kubetools_config = load_kubetools_config(
            app_dir,
            env=build.env,
            namespace=build.namespace,
        )

        context_to_image = ensure_docker_images(
            kubetools_config, build, app_dir,
            commit_hash=commit_hash,
            default_registry=registry,
        )

        services, deployments, jobs = generate_kubernetes_configs_for_project(
            kubetools_config,
            envvars=envvars,
            context_name_to_image=context_to_image,
            base_annotations=annotations,
            replicas=replicas,
        )

        all_services.extend(services)
        all_deployments.extend(deployments)
        all_jobs.extend(jobs)

    if dry:
        return _dry_deploy_loop(build, all_services, all_deployments, all_jobs)

    log_deploy_changes(
        build, all_services, all_deployments, all_jobs,
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
        all_services,
        all_deployments,
        all_jobs,
    )


def _get_objects_to_delete(
@cli_bootstrap.command(help_priority=1)
    object_type, list_objects_function,
    build, app_names,
    check_leftovers=True,
):
    objects_to_delete = list_objects_function(build)

    if app_names:
        objects_to_delete = list(filter(
            lambda obj: obj.metadata.labels.get('kubetools/name') in app_names,
            objects_to_delete,
        ))

        if check_leftovers:
            object_names_to_delete = set([
                obj.metadata.labels['kubetools/name']
                for obj in objects_to_delete
            ])

            leftover_app_names = set(app_names) - object_names_to_delete
            if leftover_app_names:
                raise click.BadParameter(f'{object_type} not found {leftover_app_names}')

    return objects_to_delete


@click.option(
    '-y', '--yes',
    is_flag=True,
    default=False,
    help='Flag to auto-yes remove confirmation step.',
)
@click.option(
    '--cleanup', 'do_cleanup',
    is_flag=True,
    default=False,
    help='Run a cleanup immediately after removal.',
)
@click.argument('namespace')
@click.argument('app_names', nargs=-1)
@click.pass_context
def remove(ctx, yes, do_cleanup, namespace, app_names):
    '''
    Removes one or more apps from a given namespace.
    '''

    build = Build(
        env=ctx.meta['kube_context'],
        namespace=namespace,
    )

    services_to_delete = _get_objects_to_delete(
        'Services', list_services, build, app_names,
    )

    deployments_to_delete = _get_objects_to_delete(
        'Deployments', list_deployments, build, app_names,
    )

    jobs_to_delete = _get_objects_to_delete(
        'Jobs', list_jobs, build, app_names,
        check_leftovers=False,
    )

    if not any((services_to_delete, deployments_to_delete, jobs_to_delete)):
        click.echo('Nothing to do!')
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
    Cleans up a namespace by removing any orphaned objects and stale jobs.
    '''

    build = Build(
        env=ctx.meta['kube_context'],
        namespace=namespace,
    )

    replica_sets_to_delete, pods_to_delete = get_cleanup_objects(build)

    if not any((replica_sets_to_delete, pods_to_delete)):
        click.echo('Nothing to do!')
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


# @cli_bootstrap.command()
# @click.argument('app_names', nargs=-1)
# def restart(namespace, app_names):
#     '''
#     Restarts one or more apps in a given namespace.
#     '''
