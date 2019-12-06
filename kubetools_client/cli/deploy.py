import os

import click

from kubetools_client.cli import cli_bootstrap
from kubetools_client.config import load_kubetools_config
from kubetools_client.deploy import deploy_or_upgrade
from kubetools_client.deploy.build import Build
from kubetools_client.deploy.image import ensure_docker_images
from kubetools_client.deploy.kubernetes.config import generate_kubernetes_configs_for_project
from kubetools_client.deploy.util import run_shell_command


@cli_bootstrap.command(help_priority=0)
@click.argument('namespace')
@click.argument('app_dirs', nargs=-1, type=click.Path(exists=True, file_okay=False))
@click.pass_context
def deploy(ctx, namespace, app_dirs):
    '''
    Deploy an app, or apps, to Kubernetes.
    '''

    if not app_dirs:
        app_dirs = (os.getcwd(),)

    build = Build(
        env=ctx.meta['kube_context'],
        namespace=namespace,
    )

    all_depend_services = []
    all_main_services = []
    all_depend_deployments = []
    all_main_deployments = []
    all_jobs = []

    for app_dir in app_dirs:
        kubetools_config = load_kubetools_config(
            app_dir,
            env=build.env,
            namespace=build.namespace,
        )

        commit_hash = run_shell_command(
            'git', 'rev-parse', '--short=7', 'HEAD',
            cwd=app_dir,
        ).strip().decode()

        branch_name = run_shell_command(
            'git', 'rev-parse', '--abbrev-ref', 'HEAD',
            cwd=app_dir,
        ).strip().decode()

        annotations = {
            'kube_env': build.env,
            'kube_namespace': build.namespace,
            'version': branch_name,
        }

        labels = {
            'project_name': kubetools_config['name'],
        }

        # TODO: is this needed anymore? Deployment lifecycle means selecting via
        # git commit no longer needed. This pre-dates deployments.
        deployment_labels = {
            'git_commit': commit_hash,
        }

        envvars = {
            'KUBE': 'true',
            'KUBE_NAMESPACE': build.namespace,
            'KUBE_ENV': build.env,
        }

        context_to_image = ensure_docker_images(
            kubetools_config, build, app_dir,
            commit_hash=commit_hash,
            default_registry=ctx.meta['default_registry'],
        )

        (
            (depend_services, main_services),
            (depend_deployments, main_deployments),
            jobs,
        ) = generate_kubernetes_configs_for_project(
            kubetools_config,
            envvars=envvars,
            context_name_to_image=context_to_image,
            base_annotations=annotations,
            base_labels=labels,
            deployment_labels=deployment_labels,
        )

        all_depend_services.extend(depend_services)
        all_depend_deployments.extend(depend_deployments)
        all_main_services.extend(main_services)
        all_main_deployments.extend(main_deployments)
        all_jobs.extend(jobs)

    deploy_or_upgrade(
        build,
        all_depend_services,
        all_depend_deployments,
        all_main_services,
        all_main_deployments,
        all_jobs,
    )


# @cli_bootstrap.command()
# @click.argument('app_names', nargs=-1)
# def remove(namespace, app_names):
#     '''
#     Removes one or more apps from a given namespace.
#     '''


# @cli_bootstrap.command()
# @click.argument('app_names', nargs=-1)
# def restart(namespace, app_names):
#     '''
#     Restarts one or more apps in a given namespace.
#     '''


# @cli_bootstrap.command()
# @click.argument('app_names', nargs=-1)
# def cleanup(namespace, app_names):
#     '''
#     Cleans up a namespace by removing any orphaned objects and stale jobs.
#     '''
