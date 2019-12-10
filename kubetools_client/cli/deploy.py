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
@click.option(
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
@click.argument('namespace')
@click.argument(
    'app_dirs',
    nargs=-1,
    type=click.Path(exists=True, file_okay=False),
)
@click.pass_context
def deploy(ctx, dry, replicas, registry, namespace, app_dirs):
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
            'kubetools/env': build.env,
            'kubetools/namespace': build.namespace,
            'kubetools/git_commit': commit_hash,
            'app.kubernetes.io/managed-by': 'kubetools',
        }

        if branch_name != 'HEAD':
            annotations['kubetools/git_branch'] = branch_name

        try:
            annotations['kubetools/git_tag'] = run_shell_command(
                'git', 'tag', '--points-at', commit_hash,
                cwd=app_dir,
            ).strip().decode()
        except KubeBuildError:
            pass

        labels = {
            'kubetools/project_name': kubetools_config['name'],
        }

        envvars = {
            'KUBE': 'true',
            'KUBE_NAMESPACE': build.namespace,
            'KUBE_ENV': build.env,
        }

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
            base_labels=labels,
            replicas=replicas,
        )

        all_services.extend(services)
        all_deployments.extend(deployments)
        all_jobs.extend(jobs)

    deploy_or_upgrade(
        build,
        all_services,
        all_deployments,
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
