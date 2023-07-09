from kubetools.cli.git_utils import get_git_info
from kubetools.config import load_kubetools_config
from kubetools.constants import (
    ROLE_LABEL_KEY,
)
from kubetools.deploy.image import ensure_docker_images
from kubetools.deploy.util import log_actions
from kubetools.kubernetes.api import (
    create_cronjob,
    create_deployment,
    create_job,
    create_namespace,
    create_service,
    cronjob_exists,
    delete_job,
    deployment_exists,
    get_object_name,
    list_cronjobs,
    list_deployments,
    list_namespaces,
    list_services,
    namespace_exists,
    service_exists,
    update_cronjob,
    update_deployment,
    update_namespace,
    update_service,
)
from kubetools.kubernetes.config import (
    generate_kubernetes_configs_for_project,
    generate_namespace_config,
)


# Deploy/upgrade
# Handles deploying new services and upgrading existing ones

def get_deploy_objects(
    build,
    app_dirs,
    replicas=None,
    default_registry=None,
    build_args=None,
    extra_envvars=None,
    extra_annotations=None,
    ignore_git_changes=False,
    custom_config_file=False,
):
    all_services = []
    all_deployments = []
    all_jobs = []
    all_cronjobs = []

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

    for app_dir in app_dirs:
        commit_hash, git_annotations = get_git_info(app_dir, ignore_git_changes)
        annotations.update(git_annotations)

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
            build_args=build_args,
        )

        services, deployments, jobs, cronjobs = generate_kubernetes_configs_for_project(
            kubetools_config,
            envvars=envvars,
            context_name_to_image=context_to_image,
            base_annotations=annotations,
            replicas=replicas or 1,
            default_registry=default_registry,
        )

        all_services.extend(services)
        all_deployments.extend(deployments)
        all_jobs.extend(jobs)
        all_cronjobs.extend(cronjobs)

    existing_deployments = {
        get_object_name(deployment): deployment
        for deployment in list_deployments(build.env, build.namespace)
    }

    # If we haven't been provided an explicit number of replicas, default to using
    # anything that exists live when available.
    if replicas is None:
        for deployment in all_deployments:
            existing_deployment = existing_deployments.get(get_object_name(deployment))
            if existing_deployment:
                deployment['spec']['replicas'] = existing_deployment.spec.replicas

    return namespace, all_services, all_deployments, all_jobs, all_cronjobs


def log_deploy_changes(
    build, namespace, services, deployments, jobs, cronjobs,
    message='Executing changes:',
    name_formatter=lambda name: name,
):
    existing_namespace_names = set(
        get_object_name(namespace)
        for namespace in list_namespaces(build.env)
    )
    existing_service_names = set(
        get_object_name(service)
        for service in list_services(build.env, build.namespace)
    )
    existing_deployment_names = set(
        get_object_name(deployment)
        for deployment in list_deployments(build.env, build.namespace)
    )
    existing_cronjobs_names = set(
        get_object_name(cronjob)
        for cronjob in list_cronjobs(build.env, build.namespace)
    )

    deploy_service_names = set(
        get_object_name(service) for service in services
    )
    deploy_deployment_names = set(
        get_object_name(deployment) for deployment in deployments
    )
    deploy_cronjobs_names = set(
        get_object_name(cronjob) for cronjob in cronjobs
    )
    deploy_namespace_name = set((build.namespace,))

    new_namespace = deploy_namespace_name - existing_namespace_names

    new_services = deploy_service_names - existing_service_names
    update_services = deploy_service_names - new_services

    new_deployments = deploy_deployment_names - existing_deployment_names
    update_deployments = deploy_deployment_names - new_deployments

    new_cronjobs = deploy_cronjobs_names - existing_cronjobs_names
    update_cronjobs = deploy_cronjobs_names - new_cronjobs

    with build.stage(message):
        log_actions(build, 'CREATE', 'namespace', new_namespace, name_formatter)
        log_actions(build, 'CREATE', 'service', new_services, name_formatter)
        log_actions(build, 'CREATE', 'deployment', new_deployments, name_formatter)
        log_actions(build, 'CREATE', 'cronjob', new_cronjobs, name_formatter)
        log_actions(build, 'UPDATE', 'service', update_services, name_formatter)
        log_actions(build, 'UPDATE', 'deployment', update_deployments, name_formatter)
        log_actions(build, 'UPDATE', 'cronjob', update_cronjobs, name_formatter)


def execute_deploy(
    build,
    namespace,
    services,
    deployments,
    jobs,
    cronjobs,
    delete_completed_jobs=True,
):
    # Split services + deployments into app (main) and dependencies
    depend_services = []
    main_services = []

    for service in services:
        if service['metadata']['labels'][ROLE_LABEL_KEY] == 'app':
            main_services.append(service)
        else:
            depend_services.append(service)

    depend_deployments = []
    main_deployments = []
    for deployment in deployments:
        if deployment['metadata']['labels'][ROLE_LABEL_KEY] == 'app':
            main_deployments.append(deployment)
        else:
            depend_deployments.append(deployment)

    # Now execute the deploy process
    if namespace:
        with build.stage('Create and/or update namespace'):
            if namespace_exists(build.env, namespace):
                build.log_info(f'Update namespace: {get_object_name(namespace)}')
                update_namespace(build.env, namespace)
            else:
                build.log_info(f'Create namespace: {get_object_name(namespace)}')
                create_namespace(build.env, namespace)

    if depend_services:
        with build.stage('Create and/or update dependency services'):
            for service in depend_services:
                if service_exists(build.env, build.namespace, service):
                    build.log_info(f'Update service: {get_object_name(service)}')
                    update_service(build.env, build.namespace, service)
                else:
                    build.log_info(f'Create service: {get_object_name(service)}')
                    create_service(build.env, build.namespace, service)

    if depend_deployments:
        with build.stage('Create and/or update dependency deployments'):
            for deployment in depend_deployments:
                if deployment_exists(build.env, build.namespace, deployment):
                    build.log_info(f'Update deployment: {get_object_name(deployment)}')
                    update_deployment(build.env, build.namespace, deployment)
                else:
                    build.log_info(f'Create deployment: {get_object_name(deployment)}')
                    create_deployment(build.env, build.namespace, deployment)

    noexist_main_services = []
    exist_main_services = []
    for service in main_services:
        if not service_exists(build.env, build.namespace, service):
            noexist_main_services.append(service)
        else:
            exist_main_services.append(service)

    if noexist_main_services:
        with build.stage('Create any app services that do not exist'):
            for service in noexist_main_services:
                build.log_info(f'Create service: {get_object_name(service)}')
                create_service(build.env, build.namespace, service)

    noexist_main_deployments = []
    exist_main_deployments = []
    for deployment in main_deployments:
        if not deployment_exists(build.env, build.namespace, deployment):
            noexist_main_deployments.append(deployment)
        else:
            exist_main_deployments.append(deployment)

    if noexist_main_deployments:
        with build.stage('Create any app deployments that do not exist'):
            for deployment in noexist_main_deployments:
                build.log_info(f'Create deployment: {get_object_name(deployment)}')
                create_deployment(build.env, build.namespace, deployment)

    if jobs:
        with build.stage('Execute upgrades'):
            for job in jobs:
                build.log_info(f'Create job: {get_object_name(job)}')
                create_job(build.env, build.namespace, job)
                if delete_completed_jobs:
                    delete_job(build.env, build.namespace, job)

    if exist_main_deployments:
        with build.stage('Update existing app deployments'):
            for deployment in exist_main_deployments:
                build.log_info(f'Update deployment: {get_object_name(deployment)}')
                update_deployment(build.env, build.namespace, deployment)

    if exist_main_services:
        with build.stage('Update existing app services'):
            for service in exist_main_services:
                build.log_info(f'Update service: {get_object_name(service)}')
                update_service(build.env, build.namespace, service)

    for cronjob in cronjobs:
        with build.stage('Create and/or update cronjobs'):
            if cronjob_exists(build.env, build.namespace, cronjob):
                build.log_info(f'Update cronjob: {get_object_name(cronjob)}')
                update_cronjob(build.env, build.namespace, cronjob)
            else:
                build.log_info(f'Create cronjob: {get_object_name(cronjob)}')
                create_cronjob(build.env, build.namespace, cronjob)
