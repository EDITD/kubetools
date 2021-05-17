from os import path

from kubetools.config import load_kubetools_config
from kubetools.deploy.image import ensure_docker_images
from kubetools.deploy.util import log_actions
from kubetools.exceptions import KubeBuildError
from kubetools.kubernetes.api import (
    create_job,
    create_namespace,
    delete_job,
    get_object_name,
    list_namespaces,
    namespace_exists,
    update_namespace,
)
from kubetools.kubernetes.config import generate_namespace_config
from kubetools.kubernetes.config.job import make_job_config

from .util import get_git_info, is_git_committed


# Run
# Create a Kubernetes job from an app + container context

def get_run_objects(
    build,
    app_dir,
    container_context,
    command,
    default_registry=None,
    extra_envvars=None,
    extra_annotations=None,
    ignore_git_changes=False,
    custom_config_file=False,
):
    envvars = {
        'KUBE_ENV': build.env,
        'KUBE_NAMESPACE': build.namespace,
    }
    if extra_envvars:
        envvars.update(extra_envvars)

    annotations = {
        'kubetools/env': build.env,
        'kubetools/namespace': build.namespace,
    }
    if extra_annotations:
        annotations.update(extra_annotations)

    namespace = generate_namespace_config(build.namespace, base_annotations=annotations)

    if path.exists(path.join(app_dir, '.git')):
        if not is_git_committed(app_dir) and not ignore_git_changes:
            raise KubeBuildError(f'{app_dir} contains uncommitted changes, refusing to deploy!')

        commit_hash, git_annotations = get_git_info(app_dir)
        annotations.update(git_annotations)
    else:
        raise KubeBuildError(f'{app_dir} is not a valid git repository!')

    kubetools_config = load_kubetools_config(
        app_dir,
        env=build.env,
        namespace=build.namespace,
        app_name=app_dir,
        custom_config_file=custom_config_file,
    )

    context_to_image = ensure_docker_images(
        kubetools_config, build, app_dir,
        commit_hash=commit_hash,
        default_registry=default_registry,
    )

    job = make_job_config({
        'image': context_to_image[container_context],
        'command': command,
    })

    return namespace, job


def log_run_changes(
    build, namespace, job,
    message='Executing changes:',
    name_formatter=lambda name: name,
):
    existing_namespace_names = set(
        get_object_name(namespace)
        for namespace in list_namespaces(build.env)
    )

    deploy_namespace_name = set((build.namespace,))

    new_namespace = deploy_namespace_name - existing_namespace_names

    with build.stage(message):
        log_actions(build, 'CREATE', 'namespace', new_namespace, name_formatter)
        log_actions(build, 'CREATE', 'job', [job], name_formatter)


def execute_run(build, namespace, job, wait_for_job=False, delete_completed_job=False):
    if namespace:
        with build.stage('Create and/or update namespace'):
            if namespace_exists(build.env, namespace):
                build.log_info(f'Update namespace: {get_object_name(namespace)}')
                update_namespace(build.env, namespace)
            else:
                build.log_info(f'Create namespace: {get_object_name(namespace)}')
                create_namespace(build.env, namespace)

    with build.stage('Execute job'):
        build.log_info(f'Create job: {get_object_name(job)}')
        create_job(build.env, build.namespace, job, wait=wait_for_job)
        if delete_completed_job:
            build.log_info(f'Delete job: {get_object_name(job)}')
            delete_job(build.env, build.namespace, job)
