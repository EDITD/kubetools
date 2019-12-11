from time import sleep

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from kubetools_client.exceptions import KubeBuildError
from kubetools_client.settings import get_settings


def get_object_name(obj):
    if isinstance(obj, dict):
        return obj['metadata']['name']
    return obj.metadata.name


def _get_api_client(build):
    return config.new_client_from_config(context=build.env)


def _get_k8s_core_api(build):
    api_client = _get_api_client(build)
    return client.CoreV1Api(api_client=api_client)


def _get_k8s_apps_api(build):
    api_client = _get_api_client(build)
    return client.AppsV1Api(api_client=api_client)


def _get_k8s_batch_api(build):
    api_client = _get_api_client(build)
    return client.BatchV1Api(api_client=api_client)


def _object_exists(api, method, build, obj):
    try:
        getattr(api, method)(
            namespace=build.namespace,
            name=get_object_name(obj),
        )
    except ApiException as e:
        if e.status == 404:
            return False
        raise
    return True


def list_pods(build):
    k8s_core_api = _get_k8s_core_api(build)
    return k8s_core_api.list_namespaced_pod(namespace=build.namespace).items


def delete_pod(build, pod):
    k8s_core_api = _get_k8s_core_api(build)
    return k8s_core_api.delete_namespaced_pod(
        name=get_object_name(pod),
        namespace=build.namespace,
    )


def list_replica_sets(build):
    k8s_apps_api = _get_k8s_apps_api(build)
    return k8s_apps_api.list_namespaced_replica_set(namespace=build.namespace).items


def delete_replica_set(build, replica_set):
    k8s_apps_api = _get_k8s_apps_api(build)
    return k8s_apps_api.delete_namespaced_replica_set(
        name=get_object_name(replica_set),
        namespace=build.namespace,
    )


def list_services(build):
    k8s_core_api = _get_k8s_core_api(build)
    return k8s_core_api.list_namespaced_service(namespace=build.namespace).items


def delete_service(build, service):
    k8s_core_api = _get_k8s_core_api(build)
    return k8s_core_api.delete_namespaced_service(
        name=get_object_name(service),
        namespace=build.namespace,
    )


def service_exists(build, service):
    k8s_core_api = _get_k8s_core_api(build)
    return _object_exists(k8s_core_api, 'read_namespaced_service', build, service)


def create_service(build, service):
    build.log_info(f'Create service: {get_object_name(service)}')

    k8s_core_api = _get_k8s_core_api(build)
    k8s_service = k8s_core_api.create_namespaced_service(
        body=service,
        namespace=build.namespace,
    )

    return k8s_service


def update_service(build, service):
    service_name = get_object_name(service)
    build.log_info(f'Update service: {service_name}')

    k8s_core_api = _get_k8s_core_api(build)

    # Here we are forced to replace the entire service object - unlike deployments
    # this requires specifying the clusterIP and resourceVersion that already exist.
    # We also include the existing port spec so any nodePorts don't change.
    # The alternative is one of the various "patch" methods - however none of them
    # seem to be able to *remove* labels.
    existing_service = k8s_core_api.read_namespaced_service(
        name=service_name,
        namespace=build.namespace,
    )
    service['spec']['ports'] = existing_service.spec.ports
    service['spec']['clusterIP'] = existing_service.spec.cluster_ip
    service['metadata']['resourceVersion'] = existing_service.metadata.resource_version

    k8s_service = k8s_core_api.replace_namespaced_service(
        name=service_name,
        body=service,
        namespace=build.namespace,
    )

    return k8s_service


def create_or_update_service(build, service):
    if service_exists(build, service):
        return update_service(build, service)
    return create_service(build, service)


def list_deployments(build):
    k8s_apps_api = _get_k8s_apps_api(build)
    return k8s_apps_api.list_namespaced_deployment(namespace=build.namespace).items


def delete_deployment(build, deployment):
    k8s_apps_api = _get_k8s_apps_api(build)
    return k8s_apps_api.delete_namespaced_deployment(
        name=get_object_name(deployment),
        namespace=build.namespace,
    )


def deployment_exists(build, deployment):
    k8s_apps_api = _get_k8s_apps_api(build)
    return _object_exists(k8s_apps_api, 'read_namespaced_deployment', build, deployment)


def create_deployment(build, deployment):
    build.log_info(f'Create deployment: {get_object_name(deployment)}')

    k8s_apps_api = _get_k8s_apps_api(build)
    k8s_deployment = k8s_apps_api.create_namespaced_deployment(
        body=deployment,
        namespace=build.namespace,
    )

    wait_for_deployment(build, k8s_deployment)
    return k8s_deployment


def update_deployment(build, deployment):
    build.log_info(f'Update deployment: {get_object_name(deployment)}')

    k8s_apps_api = _get_k8s_apps_api(build)
    k8s_deployment = k8s_apps_api.replace_namespaced_deployment(
        name=get_object_name(deployment),
        body=deployment,
        namespace=build.namespace,
    )

    wait_for_deployment(build, k8s_deployment)
    return k8s_deployment


def wait_for_deployment(build, deployment):
    settings = get_settings()
    k8s_apps_api = _get_k8s_apps_api(build)

    sleeps = 0

    while True:
        deployment = k8s_apps_api.read_namespaced_deployment(
            name=get_object_name(deployment),
            namespace=build.namespace,
        )

        if deployment.status.ready_replicas == deployment.status.replicas:
            break

        sleep(settings.WAIT_SLEEP_TIME)
        sleeps += 1

        if sleeps > settings.WAIT_MAX_SLEEPS:
            raise KubeBuildError('Timeout waiting for deployment to be ready')


def create_or_update_deployment(build, deployment):
    if deployment_exists(build, deployment):
        return update_deployment(build, deployment)
    return create_deployment(build, deployment)


def list_jobs(build):
    k8s_batch_api = _get_k8s_batch_api(build)
    return k8s_batch_api.list_namespaced_job(namespace=build.namespace).items


def delete_job(build, job):
    k8s_batch_api = _get_k8s_batch_api(build)
    return k8s_batch_api.delete_namespaced_job(
        name=get_object_name(job),
        namespace=build.namespace,
    )


def create_job(build, job):
    job_command = job['spec']['template']['spec']['containers'][0]['command']
    build.log_info(f'Create job: {get_object_name(job)}', job_command)

    k8s_batch_api = _get_k8s_batch_api(build)
    k8s_job = k8s_batch_api.create_namespaced_job(
        body=job,
        namespace=build.namespace,
    )

    wait_for_job(build, k8s_job)
    return k8s_job


def wait_for_job(build, job):
    settings = get_settings()
    k8s_batch_api = _get_k8s_batch_api(build)

    sleeps = 0

    while True:
        job = k8s_batch_api.read_namespaced_job(
            name=get_object_name(job),
            namespace=build.namespace,
        )

        if job.status.succeeded == job.spec.completions:
            break

        sleep(settings.WAIT_SLEEP_TIME)
        sleeps += 1

        if sleeps > settings.WAIT_MAX_SLEEPS:
            raise KubeBuildError('Timeout waiting for job to complete')
