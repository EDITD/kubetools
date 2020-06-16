from kubetools.deploy.util import delete_objects, get_app_objects, log_actions
from kubetools.kubernetes.api import (
    delete_deployment,
    delete_job,
    delete_service,
    list_deployments,
    list_jobs,
    list_services,
)


# Remove
# Handles removal of deployments, services and jobs in a namespace

def get_remove_objects(build, app_names=None, force=False):
    services_to_delete = get_app_objects(
        build,
        app_names,
        list_services,
        force=force,
    )
    deployments_to_delete = get_app_objects(
        build,
        app_names,
        list_deployments,
        force=force,
    )
    jobs_to_delete = get_app_objects(
        build,
        app_names,
        list_jobs,
        force=force,
    )

    return services_to_delete, deployments_to_delete, jobs_to_delete


def log_remove_changes(
    build, services, deployments, jobs,
    message='Executing changes:',
    name_formatter=lambda name: name,
):
    with build.stage(message):
        log_actions(build, 'DELETE', 'service', services, name_formatter)
        log_actions(build, 'DELETE', 'deployment', deployments, name_formatter)
        log_actions(build, 'DELETE', 'job', jobs, name_formatter)


def execute_remove(build, services, deployments, jobs):
    if services:
        with build.stage('Delete services'):
            delete_objects(build, services, delete_service)

    if deployments:
        with build.stage('Delete deployments'):
            delete_objects(build, deployments, delete_deployment)

    if jobs:
        with build.stage('Delete jobs'):
            delete_objects(build, jobs, delete_job)
