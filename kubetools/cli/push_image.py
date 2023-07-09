import os

import click

from kubetools.cli import cli_bootstrap
from kubetools.cli.git_utils import get_git_info
from kubetools.config import load_kubetools_config
from kubetools.deploy.build import Build
from kubetools.deploy.image import ensure_docker_images


@cli_bootstrap.command(help_priority=5)
@click.option(
    '--default-registry',
    help='Default registry for apps that do not specify.',
)
@click.option(
    'additional_tags', '-t', '--tag',
    multiple=True,
    help='Extra tags to apply to built image',
)
@click.option(
    'build_args', '-b', '--build-arg',
    multiple=True,
    help='Arguments to pass to docker build (Dockerfile ARG) as ARG=VALUE',
)
@click.pass_context
def push(ctx, default_registry, additional_tags, build_args):
    '''
    Push app images to docker repo
    '''
    build = Build(
        env=ctx.meta['kube_context'],
        namespace=None,
    )
    app_dir = os.getcwd()
    commit_hash, _ = get_git_info(app_dir)
    kubetools_config = load_kubetools_config(
        app_dir,
        env=build.env,
        namespace=build.namespace,
        app_name=app_dir,
        custom_config_file=False,
    )
    ensure_docker_images(
        kubetools_config, build, app_dir,
        commit_hash=commit_hash,
        default_registry=default_registry,
        additional_tags=additional_tags,
        build_args=build_args,
    )
