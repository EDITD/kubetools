from .kubernetes.api import (
    create_deployment,
    create_job,
    create_or_update_deployment,
    create_or_update_service,
    create_service,
    delete_deployment,
    delete_job,
    delete_pod,
    delete_replica_set,
    delete_service,
    deployment_exists,
    get_object_name,
    list_deployments,
    list_pods,
    list_replica_sets,
    list_services,
    service_exists,
    update_deployment,
    update_service,
)


def _log_actions(build, action, object_type, names, name_formatter):
    for name in names:
        if not isinstance(name, str):
            name = get_object_name(name)
        build.log_info(f'{action} {object_type} {name_formatter(name)}')


def _delete_objects(build, objects, delete_function):
    for obj in objects:
        delete_function(build, obj)

def log_deploy_changes(
    build, services, deployments,
    message='Executing changes:',
    name_formatter=lambda name: name,
):
    existing_service_names = set(
        get_object_name(service) for service in list_services(build)
    )
    existing_deployment_names = set(
        get_object_name(deployment) for deployment in list_deployments(build)
    )

    deploy_service_names = set(
        get_object_name(service) for service in services
    )
    deploy_deployment_names = set(
        get_object_name(deployment) for deployment in deployments
    )

    new_services = deploy_service_names - existing_service_names
    update_services = deploy_service_names - new_services

    new_deployments = deploy_deployment_names - existing_deployment_names
    update_deployments = deploy_deployment_names - new_deployments

    with build.stage(message):
        for service in new_services:
            build.log_info(f'CREATE service {name_formatter(service)}')
        for deployment in new_deployments:
            build.log_info(f'CREATE deployment {name_formatter(deployment)}')

        for service in update_services:
            build.log_info(f'UPDATE service {name_formatter(service)}')
        for deployment in update_deployments:
            build.log_info(f'UPDATE deployment {name_formatter(deployment)}')


def deploy_or_upgrade(build, services, deployments, jobs):
    # Split services + deployments into app (main) and dependencies
    depend_services = []
    main_services = []

    for service in services:
        if service['metadata']['labels']['kubetools/role'] == 'app':
            main_services.append(service)
        else:
            depend_services.append(service)

    depend_deployments = []
    main_deployments = []
    for deployment in deployments:
        if deployment['metadata']['labels']['kubetools/role'] == 'app':
            main_deployments.append(deployment)
        else:
            depend_deployments.append(deployment)

    # Now execute the deploy process
    if depend_services:
        with build.stage('Create and/or update dependency services'):
            for service in depend_services:
                create_or_update_service(build, service)

    if depend_deployments:
        with build.stage('Create and/or update dependency deployments'):
            for deployment in depend_deployments:
                create_or_update_deployment(build, deployment)

    noexist_main_services = []
    exist_main_services = []
    for service in main_services:
        if not service_exists(build, service):
            noexist_main_services.append(service)
        else:
            exist_main_services.append(service)

    if noexist_main_services:
        with build.stage('Create any app services that do not exist'):
            for service in noexist_main_services:
                create_service(build, service)

    noexist_main_deployments = []
    exist_main_deployments = []
    for deployment in main_deployments:
        if not deployment_exists(build, deployment):
            noexist_main_deployments.append(deployment)
        else:
            exist_main_deployments.append(deployment)

    if noexist_main_deployments:
        with build.stage('Create any app deployments that do not exist'):
            for deployment in main_deployments:
                create_deployment(build, deployment)

    if jobs:
        with build.stage('Execute upgrades'):
            for job in jobs:
                create_job(build, job)

    if exist_main_deployments:
        with build.stage('Update existing app deployments'):
            for deployment in exist_main_deployments:
                update_deployment(build, deployment)

    if exist_main_services:
        with build.stage('Update existing app services'):
            for service in exist_main_services:
                update_service(build, service)
# Cleanup
# Handles removal of orphaned replicasets and pods as well as any complete jobs

def get_cleanup_objects(build):
    replica_sets = list_replica_sets(build)
    replica_sets_to_delete = []
    replica_set_names_to_delete = set()

    for replica_set in replica_sets:
        if not replica_set.metadata.owner_references:
            replica_set_names_to_delete.add(replica_set.metadata.name)
            replica_sets_to_delete.append(replica_set)

    pods = list_pods(build)
    pods_to_delete = []

    for pod in pods:
        if not pod.metadata.owner_references:
            pods_to_delete.append(pod)
        elif len(pod.metadata.owner_references) == 1:
            owner = pod.metadata.owner_references[0]
            if owner.name in replica_set_names_to_delete:
                pods_to_delete.append(pod)

    return replica_sets_to_delete, pods_to_delete


def log_cleanup_changes(
    build, replica_sets, pods,
    message='Executing changes:',
    name_formatter=lambda name: name,
):
    with build.stage(message):
        _log_actions(build, 'DELETE', 'replica_set', replica_sets, name_formatter)
        _log_actions(build, 'DELETE', 'pod', pods, name_formatter)


def cleanup(build, replica_sets, pods):
    with build.stage('Delete replica sets'):
        _delete_objects(build, replica_sets, delete_replica_set)

    with build.stage('Delete pods'):
        _delete_objects(build, pods, delete_pod)
