from time import sleep

from kubernetes.client.rest import ApiException

from kubetools_client.settings import get_settings

from .util import get_k8s_apps_api, get_k8s_batch_api, get_k8s_core_api


def _object_exists(api, method, build, obj):
    try:
        getattr(api, method)(
            namespace=build.namespace,
            name=obj['metadata']['name'],
        )
    except ApiException as e:
        if e.status == 404:
            return False
        raise
    return True


def _service_exists(build, service):
    k8s_core_api = get_k8s_core_api(build)
    return _object_exists(k8s_core_api, 'read_namespaced_service', build, service)


def _create_service(build, service):
    build.log_info(f'Create service: {service["metadata"]["name"]}')

    k8s_core_api = get_k8s_core_api(build)
    k8s_core_api.create_namespaced_service(
        body=service,
        namespace=build.namespace,
    )


def _update_service(build, service):
    service_name = service['metadata']['name']
    build.log_info(f'Update service: {service_name}')

    # TODO: use this after https://github.com/kubernetes-client/python/pull/959
    # k8s_core_api.patch_namespaced_service(
    #     name=service_name,
    #     body=service,
    #     namespace=build.namespace,
    #     content_type='application/strategic-merge-patch+json',
    # )
    k8s_core_api = get_k8s_core_api(build)
    k8s_core_api.api_client.call_api(
        '/api/v1/namespaces/{namespace}/services/{service_name}',
        'PATCH',
        body=service,
        path_params={
            'namespace': build.namespace,
            'service_name': service_name,
        },
        header_params={
            'Content-Type': 'application/strategic-merge-patch+json',
        },
    )


def _create_or_update_service(build, service):
    if _service_exists(build, service):
        return _update_service(build, service)
    return _create_service(build, service)


def _deployment_exists(build, deployment):
    k8s_apps_api = get_k8s_apps_api(build)
    return _object_exists(k8s_apps_api, 'read_namespaced_deployment', build, deployment)


def _create_deployment(build, deployment):
    build.log_info(f'Create deployment: {deployment["metadata"]["name"]}')

    k8s_apps_api = get_k8s_apps_api(build)
    deployment = k8s_apps_api.create_namespaced_deployment(
        body=deployment,
        namespace=build.namespace,
    )

    _wait_for_deployment(build, deployment)


def _update_deployment(build, deployment):
    build.log_info(f'Update deployment: {deployment["metadata"]["name"]}')

    k8s_apps_api = get_k8s_apps_api(build)
    deployment = k8s_apps_api.replace_namespaced_deployment(
        name=deployment['metadata']['name'],
        body=deployment,
        namespace=build.namespace,
    )

    _wait_for_deployment(build, deployment)


def _wait_for_deployment(build, deployment):
    settings = get_settings()
    k8s_apps_api = get_k8s_apps_api(build)

    while True:
        deployment = k8s_apps_api.read_namespaced_deployment(
            name=deployment.metadata.name,
            namespace=build.namespace,
        )

        if deployment.status.ready_replicas == deployment.status.replicas:
            break

        sleep(settings.WAIT_SLEEP_TIME)


def _create_or_update_deployment(build, deployment):
    if _deployment_exists(build, deployment):
        return _update_deployment(build, deployment)
    return _create_deployment(build, deployment)


def _create_job(build, job):
    build.log_info(f'Create job: {job["metadata"]["name"]}')

    k8s_batch_api = get_k8s_batch_api(build)
    job = k8s_batch_api.create_namespaced_job(
        body=job,
        namespace=build.namespace,
    )

    _wait_for_job(build, job)


def _wait_for_job(build, job):
    settings = get_settings()
    k8s_batch_api = get_k8s_batch_api(build)

    while True:
        job = k8s_batch_api.read_namespaced_job(
            name=job.metadata.name,
            namespace=build.namespace,
        )

        if job.status.succeeded == job.spec.completions:
            break

        sleep(settings.WAIT_SLEEP_TIME)


def deploy_or_upgrade(
    build,
    depend_services,
    depend_deployments,
    main_services,
    main_deployments,
    jobs,
):
    if depend_services:
        build.log_info('Create and/or update dependency services')
        for service in depend_services:
            _create_or_update_service(build, service)

    if depend_deployments:
        build.log_info('Create and/or update dependency deployments')
        for deployment in depend_deployments:
            _create_or_update_deployment(build, deployment)

    noexist_main_services = []
    exist_main_services = []
    for service in main_services:
        if not _service_exists(build, service):
            noexist_main_services.append(service)
        else:
            exist_main_services.append(service)

    if noexist_main_services:
        build.log_info('Create any app services that do not exist')
        for service in noexist_main_services:
            _create_service(build, service)

    noexist_main_deployments = []
    exist_main_deployments = []
    for deployment in main_deployments:
        if not _deployment_exists(build, deployment):
            noexist_main_deployments.append(deployment)
        else:
            exist_main_deployments.append(deployment)

    if noexist_main_deployments:
        build.log_info('Create any app deployments that do not exist')
        for deployment in main_deployments:
            _create_deployment(build, deployment)

    build.log_info('Execute upgrades')
    for job in jobs:
        _create_job(build, job)

    if exist_main_services:
        build.log_info('Update app services that do not exist')
        for service in exist_main_services:
            _update_service(build, service)

    if exist_main_deployments:
        build.log_info('Update app deployments that do not exist')
        for deployment in exist_main_deployments:
            _update_deployment(build, deployment)
