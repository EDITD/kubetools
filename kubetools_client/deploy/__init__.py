from .kubernetes.api import (
    create_deployment,
    create_job,
    create_or_update_deployment,
    create_or_update_service,
    create_service,
    deployment_exists,
    service_exists,
    update_deployment,
    update_service,
)


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
