from kubetools.deploy.util import delete_objects, get_app_objects, log_actions
from kubetools.kubernetes.api import (
    delete_cronjob,
    delete_deployment,
    delete_job,
    delete_service,
    list_cronjobs,
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

    cronjobs_to_delete = get_app_objects(
        build,
        app_names,
        list_cronjobs,
        force=force,
    )

    return services_to_delete, deployments_to_delete, jobs_to_delete, cronjobs_to_delete


def log_remove_changes(
    build, services, deployments, jobs, cronjobs,
    message='Executing changes:',
    name_formatter=lambda name: name,
):
    with build.stage(message):
        log_actions(build, 'DELETE', 'service', services, name_formatter)
        log_actions(build, 'DELETE', 'deployment', deployments, name_formatter)
        log_actions(build, 'DELETE', 'job', jobs, name_formatter)
        log_actions(build, 'DELETE', 'cronjob', cronjobs, name_formatter)


def execute_remove(build, services, deployments, jobs, cronjobs):
    if services:
        with build.stage('Delete services'):
            delete_objects(build, services, delete_service)

    if deployments:
        with build.stage('Delete deployments'):
            delete_objects(build, deployments, delete_deployment)

    if jobs:
        with build.stage('Delete jobs'):
            delete_objects(build, jobs, delete_job)

    # This will delete all cronjobs associated with a project
    # Need to look into this in the future, to be able to delete individual jobs
    if cronjobs:
        with build.stage('Delete cronjobs'):
            delete_objects(build, cronjobs, delete_cronjob)
