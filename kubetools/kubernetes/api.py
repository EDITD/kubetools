from time import sleep

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from kubetools.constants import MANAGED_BY_ANNOTATION_KEY
from kubetools.exceptions import KubeBuildError
from kubetools.settings import get_settings


def get_object_labels_dict(obj):
    return obj.metadata.labels or {}


def get_object_annotations_dict(obj):
    return obj.metadata.annotations or obj.spec.template.metadata.annotations or {}


def get_object_name(obj):
    if isinstance(obj, dict):
        return obj['metadata']['name']
    return obj.metadata.name


def is_kubetools_object(obj):
    if get_object_annotations_dict(obj).get(MANAGED_BY_ANNOTATION_KEY) == 'kubetools':
        return True


def _get_api_client(env):
    return config.new_client_from_config(context=env)


def _get_k8s_core_api(env):
    api_client = _get_api_client(env)
    return client.CoreV1Api(api_client=api_client)


def _get_k8s_apps_api(env):
    api_client = _get_api_client(env)
    return client.AppsV1Api(api_client=api_client)


def _get_k8s_batch_api(env):
    api_client = _get_api_client(env)
    return client.BatchV1Api(api_client=api_client)


def _object_exists(api, method, namespace, obj):
    try:
        if namespace:
            getattr(api, method)(
                namespace=namespace,
                name=get_object_name(obj),
            )
        else:
            getattr(api, method)(
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


def namespace_exists(env, namespace_obj):
    k8s_core_api = _get_k8s_core_api(env)
    return _object_exists(k8s_core_api, 'read_namespace', None, namespace_obj)


def list_namespaces(env):
    k8s_core_api = _get_k8s_core_api(env)
    return k8s_core_api.list_namespace().items


def create_namespace(env, namespace_obj):
    k8s_core_api = _get_k8s_core_api(env)
    k8s_namespace = k8s_core_api.create_namespace(
        body=namespace_obj,
    )

    _wait_for_object(k8s_core_api, 'read_namespace', None, namespace_obj)
    return k8s_namespace


def update_namespace(env, namespace_obj):
    k8s_core_api = _get_k8s_core_api(env)
    k8s_namespace = k8s_core_api.patch_namespace(
        name=get_object_name(namespace_obj),
        body=namespace_obj,
    )

    return k8s_namespace


def delete_namespace(env, namespace, namespace_obj):
    k8s_core_api = _get_k8s_core_api(env)
    k8s_core_api.delete_namespace(
        name=get_object_name(namespace_obj),
    )

    _wait_for_no_object(k8s_core_api, 'read_namespace', None, namespace_obj)


def list_pods(env, namespace):
    k8s_core_api = _get_k8s_core_api(env)
    return k8s_core_api.list_namespaced_pod(namespace=namespace).items


def delete_pod(env, namespace, pod):
    k8s_core_api = _get_k8s_core_api(env)
    k8s_core_api.delete_namespaced_pod(
        name=get_object_name(pod),
        namespace=namespace,
    )

    _wait_for_no_object(k8s_core_api, 'read_namespaced_pod', namespace, pod)


def list_replica_sets(env, namespace):
    k8s_apps_api = _get_k8s_apps_api(env)
    return k8s_apps_api.list_namespaced_replica_set(namespace=namespace).items


def delete_replica_set(env, namespace, replica_set):
    k8s_apps_api = _get_k8s_apps_api(env)
    k8s_apps_api.delete_namespaced_replica_set(
        name=get_object_name(replica_set),
        namespace=namespace,
    )

    _wait_for_no_object(k8s_apps_api, 'read_namespaced_replica_set', namespace, replica_set)


def list_services(env, namespace):
    k8s_core_api = _get_k8s_core_api(env)
    return k8s_core_api.list_namespaced_service(namespace=namespace).items


def delete_service(env, namespace, service):
    k8s_core_api = _get_k8s_core_api(env)
    k8s_core_api.delete_namespaced_service(
        name=get_object_name(service),
        namespace=namespace,
    )

    _wait_for_no_object(k8s_core_api, 'read_namespaced_service', namespace, service)


def service_exists(env, namespace, service):
    k8s_core_api = _get_k8s_core_api(env)
    return _object_exists(k8s_core_api, 'read_namespaced_service', namespace, service)


def create_service(env, namespace, service):
    k8s_core_api = _get_k8s_core_api(env)
    k8s_service = k8s_core_api.create_namespaced_service(
        body=service,
        namespace=namespace,
    )

    _wait_for_object(k8s_core_api, 'read_namespaced_service', namespace, service)
    return k8s_service


def update_service(env, namespace, service):
    k8s_core_api = _get_k8s_core_api(env)
    k8s_service = k8s_core_api.patch_namespaced_service(
        name=get_object_name(service),
        body=service,
        namespace=namespace,
    )

    return k8s_service


def list_deployments(env, namespace):
    k8s_apps_api = _get_k8s_apps_api(env)
    return k8s_apps_api.list_namespaced_deployment(namespace=namespace).items


def delete_deployment(env, namespace, deployment):
    k8s_apps_api = _get_k8s_apps_api(env)
    k8s_apps_api.delete_namespaced_deployment(
        name=get_object_name(deployment),
        namespace=namespace,
    )

    _wait_for_no_object(k8s_apps_api, 'read_namespaced_deployment', namespace, deployment)


def deployment_exists(env, namespace, deployment):
    k8s_apps_api = _get_k8s_apps_api(env)
    return _object_exists(k8s_apps_api, 'read_namespaced_deployment', namespace, deployment)


def create_deployment(env, namespace, deployment):
    k8s_apps_api = _get_k8s_apps_api(env)
    k8s_deployment = k8s_apps_api.create_namespaced_deployment(
        body=deployment,
        namespace=namespace,
    )

    wait_for_deployment(env, namespace, k8s_deployment)
    return k8s_deployment


def update_deployment(env, namespace, deployment):
    k8s_apps_api = _get_k8s_apps_api(env)
    k8s_deployment = k8s_apps_api.patch_namespaced_deployment(
        name=get_object_name(deployment),
        body=deployment,
        namespace=namespace,
    )

    wait_for_deployment(env, namespace, k8s_deployment)
    return k8s_deployment


def wait_for_deployment(env, namespace, deployment):
    k8s_apps_api = _get_k8s_apps_api(env)

    def check_deployment():
        d = k8s_apps_api.read_namespaced_deployment(
            name=get_object_name(deployment),
            namespace=namespace,
        )

        if d.status.ready_replicas == d.status.replicas:
            return True

    _wait_for(check_deployment, get_object_name(deployment))


def list_cronjobs(env, namespace):
    k8s_batch_api = _get_k8s_batch_api(env)
    return k8s_batch_api.list_namespaced_cron_job(namespace=namespace).items


def delete_cronjob(env, namespace, cronjob):
    k8s_batch_api = _get_k8s_batch_api(env)
    k8s_batch_api.delete_namespaced_cron_job(
        name=get_object_name(cronjob),
        namespace=namespace,
    )

    _wait_for_no_object(k8s_batch_api, 'read_namespaced_cron_job', namespace, cronjob)


def cronjob_exists(env, namespace, cronjob):
    k8s_batch_api = _get_k8s_batch_api(env)
    return _object_exists(k8s_batch_api, 'read_namespaced_cron_job', namespace, cronjob)


def create_cronjob(env, namespace, cronjob, wait_for_completion=True):
    k8s_batch_api = _get_k8s_batch_api(env)
    k8s_cronjob = k8s_batch_api.create_namespaced_cron_job(
        body=cronjob,
        namespace=namespace,
    )

    if wait_for_completion:
        wait_for_cron_job(env, namespace, k8s_cronjob)
    return k8s_cronjob


def update_cronjob(env, namespace, cronjob):
    k8s_batch_api = _get_k8s_batch_api(env)
    k8s_cronjob = k8s_batch_api.patch_namespaced_cron_job(
        name=get_object_name(cronjob),
        body=cronjob,
        namespace=namespace,
    )

    wait_for_cron_job(env, namespace, k8s_cronjob)
    return k8s_cronjob


def wait_for_cron_job(env, namespace, cronjob):
    k8s_batch_api = _get_k8s_batch_api(env)

    def check_cronjob():
        cj = k8s_batch_api.read_namespaced_cron_job(
            name=get_object_name(cronjob),
            namespace=namespace,
        )

        if cj.status.last_schedule_time is not None and cj.status.last_successful_time is not None:
            if cj.status.last_schedule_time <= cj.status.last_successful_time:
                return True

    _wait_for(check_cronjob, get_object_name(cronjob))


def list_jobs(env, namespace):
    k8s_batch_api = _get_k8s_batch_api(env)
    return k8s_batch_api.list_namespaced_job(namespace=namespace).items


def is_running(job):
    conditions = job.status.conditions
    if conditions is None:
        return True
    complete = any(condition.type == 'Complete' for condition in job.status.conditions)
    return not complete


def list_running_jobs(env, namespace):
    jobs = list_jobs(env, namespace)
    return [job for job in jobs if is_running(job)]


def list_complete_jobs(env, namespace):
    jobs = list_jobs(env, namespace)
    return [job for job in jobs if not is_running(job)]


valid_propagation_policies = ["Orphan", "Background", "Foreground"]


def delete_job(env, namespace, job, propagation_policy=None):
    if propagation_policy and propagation_policy not in valid_propagation_policies:
        raise KubeBuildError(f"Propagation policy must be one of {valid_propagation_policies}")
    args = {}
    if propagation_policy:
        args['propagation_policy'] = propagation_policy
    k8s_batch_api = _get_k8s_batch_api(env)
    k8s_batch_api.delete_namespaced_job(
        name=get_object_name(job),
        namespace=namespace,
        **args,
    )

    _wait_for_no_object(k8s_batch_api, 'read_namespaced_job', namespace, job)


def create_job(env, namespace, job, wait_for_completion=True):
    k8s_batch_api = _get_k8s_batch_api(env)
    k8s_job = k8s_batch_api.create_namespaced_job(
        body=job,
        namespace=namespace,
    )

    if wait_for_completion:
        wait_for_job(env, namespace, k8s_job)
    return k8s_job


def wait_for_job(env, namespace, job):
    k8s_batch_api = _get_k8s_batch_api(env)

    def check_job():
        j = k8s_batch_api.read_namespaced_job(
            name=get_object_name(job),
            namespace=namespace,
        )

        if j.status.succeeded == j.spec.completions:
            return True

    _wait_for(check_job, get_object_name(job))
