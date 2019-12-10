from time import sleep

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from kubetools_client.exceptions import KubeBuildError
from kubetools_client.settings import get_settings


def _get_api_client(build):
    return config.new_client_from_config(context=build.env)


def get_k8s_core_api(build):
    api_client = _get_api_client(build)
    return client.CoreV1Api(api_client=api_client)


def get_k8s_apps_api(build):
    api_client = _get_api_client(build)
    return client.AppsV1beta1Api(api_client=api_client)


def get_k8s_batch_api(build):
    api_client = _get_api_client(build)
    return client.BatchV1Api(api_client=api_client)


def object_exists(api, method, build, obj):
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


def service_exists(build, service):
    k8s_core_api = get_k8s_core_api(build)
    return object_exists(k8s_core_api, 'read_namespaced_service', build, service)


def create_service(build, service):
    build.log_info(f'Create service: {service["metadata"]["name"]}')

    k8s_core_api = get_k8s_core_api(build)
    k8s_core_api.create_namespaced_service(
        body=service,
        namespace=build.namespace,
    )


def update_service(build, service):
    service_name = service['metadata']['name']
    build.log_info(f'Update service: {service_name}')

    k8s_core_api = get_k8s_core_api(build)

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

    k8s_core_api.replace_namespaced_service(
        name=service_name,
        body=service,
        namespace=build.namespace,
    )


def create_or_update_service(build, service):
    if service_exists(build, service):
        return update_service(build, service)
    return create_service(build, service)


def deployment_exists(build, deployment):
    k8s_apps_api = get_k8s_apps_api(build)
    return object_exists(k8s_apps_api, 'read_namespaced_deployment', build, deployment)


def create_deployment(build, deployment):
    build.log_info(f'Create deployment: {deployment["metadata"]["name"]}')

    k8s_apps_api = get_k8s_apps_api(build)
    deployment = k8s_apps_api.create_namespaced_deployment(
        body=deployment,
        namespace=build.namespace,
    )

    wait_for_deployment(build, deployment)


def update_deployment(build, deployment):
    build.log_info(f'Update deployment: {deployment["metadata"]["name"]}')

    k8s_apps_api = get_k8s_apps_api(build)
    deployment = k8s_apps_api.replace_namespaced_deployment(
        name=deployment['metadata']['name'],
        body=deployment,
        namespace=build.namespace,
    )

    wait_for_deployment(build, deployment)


def wait_for_deployment(build, deployment):
    settings = get_settings()
    k8s_apps_api = get_k8s_apps_api(build)

    sleeps = 0

    while True:
        deployment = k8s_apps_api.read_namespaced_deployment(
            name=deployment.metadata.name,
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


def create_job(build, job):
    job_command = job['spec']['template']['spec']['containers'][0]['command']
    build.log_info(f'Create job: {job["metadata"]["name"]}', job_command)

    k8s_batch_api = get_k8s_batch_api(build)
    job = k8s_batch_api.create_namespaced_job(
        body=job,
        namespace=build.namespace,
    )

    wait_for_job(build, job)


def wait_for_job(build, job):
    settings = get_settings()
    k8s_batch_api = get_k8s_batch_api(build)

    sleeps = 0

    while True:
        job = k8s_batch_api.read_namespaced_job(
            name=job.metadata.name,
            namespace=build.namespace,
        )

        if job.status.succeeded == job.spec.completions:
            break

        sleep(settings.WAIT_SLEEP_TIME)
        sleeps += 1

        if sleeps > settings.WAIT_MAX_SLEEPS:
            raise KubeBuildError('Timeout waiting for job to complete')
