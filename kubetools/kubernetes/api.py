from time import sleep

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from kubetools.constants import MANAGED_BY_ANNOTATION_KEY
from kubetools.exceptions import KubeBuildError
from kubetools.settings import get_settings


def get_object_labels_dict(obj):
    return obj.metadata.labels or {}


def get_object_annotations_dict(obj):
    return obj.metadata.annotations or {}


def get_object_name(obj):
    if isinstance(obj, dict):
        return obj['metadata']['name']
    return obj.metadata.name


def is_kubetools_object(obj):
    if get_object_annotations_dict(obj).get(MANAGED_BY_ANNOTATION_KEY) == 'kubetools':
        return True


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


def _wait_for(function, name='object'):
    settings = get_settings()

    sleeps = 0
    while True:
        if function():
            return

        sleep(settings.WAIT_SLEEP_TIME)
        sleeps += 1

        if sleeps > settings.WAIT_MAX_SLEEPS:
            raise KubeBuildError(f'Timeout waiting for {name} to be ready')


def _wait_for_object(*args):
    return _wait_for(lambda: _object_exists(*args) is True)


def _wait_for_no_object(*args):
    return _wait_for(lambda: _object_exists(*args) is False)


def list_pods(build):
    k8s_core_api = _get_k8s_core_api(build)
    return k8s_core_api.list_namespaced_pod(namespace=build.namespace).items


def delete_pod(build, pod):
    build.log_info(f'Delete pod: {get_object_name(pod)}')

    k8s_core_api = _get_k8s_core_api(build)
    k8s_core_api.delete_namespaced_pod(
        name=get_object_name(pod),
        namespace=build.namespace,
    )

    _wait_for_no_object(k8s_core_api, 'read_namespaced_pod', build, pod)


def list_replica_sets(build):
    k8s_apps_api = _get_k8s_apps_api(build)
    return k8s_apps_api.list_namespaced_replica_set(namespace=build.namespace).items


def delete_replica_set(build, replica_set):
    build.log_info(f'Delete replica set: {get_object_name(replica_set)}')

    k8s_apps_api = _get_k8s_apps_api(build)
    k8s_apps_api.delete_namespaced_replica_set(
        name=get_object_name(replica_set),
        namespace=build.namespace,
    )

    _wait_for_no_object(k8s_apps_api, 'read_namespaced_replica_set', build, replica_set)


def list_services(build):
    k8s_core_api = _get_k8s_core_api(build)
    return k8s_core_api.list_namespaced_service(namespace=build.namespace).items


def delete_service(build, service):
    build.log_info(f'Delete service: {get_object_name(service)}')

    k8s_core_api = _get_k8s_core_api(build)
    k8s_core_api.delete_namespaced_service(
        name=get_object_name(service),
        namespace=build.namespace,
    )

    _wait_for_no_object(k8s_core_api, 'read_namespaced_service', build, service)


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

    _wait_for_object(k8s_core_api, 'read_namespaced_service', build, service)
    return k8s_service


def update_service(build, service):
    service_name = get_object_name(service)
    build.log_info(f'Update service: {service_name}')

    k8s_core_api = _get_k8s_core_api(build)
    k8s_service = k8s_core_api.patch_namespaced_service(
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
    build.log_info(f'Delete deployment: {get_object_name(deployment)}')

    k8s_apps_api = _get_k8s_apps_api(build)
    k8s_apps_api.delete_namespaced_deployment(
        name=get_object_name(deployment),
        namespace=build.namespace,
    )

    _wait_for_no_object(k8s_apps_api, 'read_namespaced_deployment', build, deployment)


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
    k8s_deployment = k8s_apps_api.patch_namespaced_deployment(
        name=get_object_name(deployment),
        body=deployment,
        namespace=build.namespace,
    )

    wait_for_deployment(build, k8s_deployment)
    return k8s_deployment


def wait_for_deployment(build, deployment):
    k8s_apps_api = _get_k8s_apps_api(build)

    def check_deployment():
        d = k8s_apps_api.read_namespaced_deployment(
            name=get_object_name(deployment),
            namespace=build.namespace,
        )

        if d.status.ready_replicas == d.status.replicas:
            return True

    _wait_for(check_deployment, get_object_name(deployment))


def create_or_update_deployment(build, deployment):
    if deployment_exists(build, deployment):
        return update_deployment(build, deployment)
    return create_deployment(build, deployment)


def list_jobs(build):
    k8s_batch_api = _get_k8s_batch_api(build)
    return k8s_batch_api.list_namespaced_job(namespace=build.namespace).items


def delete_job(build, job):
    build.log_info(f'Delete job: {get_object_name(job)}')

    k8s_batch_api = _get_k8s_batch_api(build)
    k8s_batch_api.delete_namespaced_job(
        name=get_object_name(job),
        namespace=build.namespace,
    )

    _wait_for_no_object(k8s_batch_api, 'read_namespaced_job', build, job)


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
    k8s_batch_api = _get_k8s_batch_api(build)

    def check_job():
        j = k8s_batch_api.read_namespaced_job(
            name=get_object_name(job),
            namespace=build.namespace,
        )

        if j.status.succeeded == j.spec.completions:
            return True

    _wait_for(check_job, get_object_name(job))
