from kubetools.deploy.util import delete_objects, log_actions
from kubetools.kubernetes.api import (
    delete_job,
    delete_namespace,
    delete_pod,
    delete_replica_set,
    get_object_name,
    is_kubetools_object,
    list_complete_jobs,
    list_namespaces,
    list_pods,
    list_replica_sets,
)


# Cleanup
# Handles removal of orphaned replicasets/pods and optionally any complete jobs,
# working on the namespace level only (no apps).
# If the cleanup removes all remaining objects, the namespace will be deleted too.

def get_cleanup_objects(build, cleanup_jobs):
    replica_sets = list_replica_sets(build.env, build.namespace)
    replica_set_names = set(get_object_name(replica_set) for replica_set in replica_sets)
    replica_sets_to_delete = []
    replica_set_names_to_delete = set()
    replica_set_names_already_deleted = set()

    for replica_set in replica_sets:
        if not is_kubetools_object(replica_set):
            continue

        if not replica_set.metadata.owner_references:
            replica_set_names_to_delete.add(get_object_name(replica_set))
            replica_sets_to_delete.append(replica_set)

        if replica_set.metadata.deletion_timestamp:
            replica_set_names_already_deleted.add(get_object_name(replica_set))

    jobs_to_delete = []
    jobs_set_names_to_delete = set()
    if cleanup_jobs:
        jobs_to_delete = list_complete_jobs(build.env, build.namespace)
        for job in jobs_to_delete:
            jobs_set_names_to_delete.add(get_object_name(job))

    pods = list_pods(build.env, build.namespace)
    pod_names = set(get_object_name(pod) for pod in pods)
    pods_to_delete = []
    pod_names_to_delete = set()
    pod_names_already_deleted = set()

    for pod in pods:
        if not pod.metadata.owner_references:
            pods_to_delete.append(pod)
            pod_names_to_delete.add(get_object_name(pod))

        elif len(pod.metadata.owner_references) == 1:
            owner = pod.metadata.owner_references[0]
            if owner.name in replica_set_names_to_delete or owner.name in jobs_set_names_to_delete:
                pods_to_delete.append(pod)
                pod_names_to_delete.add(get_object_name(pod))

        if pod.metadata.deletion_timestamp:
            pod_names_already_deleted.add(get_object_name(pod))

    namespaces = list_namespaces(build.env)
    for namespace in namespaces:
        if namespace.metadata.name == build.namespace:
            current_namespace = namespace
            break
    else:
        current_namespace = None

    namespace_to_delete = []
    # Namespace must exist. And "default" namespace can't be deleted
    if current_namespace and current_namespace.metadata.name != "default":
        remaining_pods = pod_names - pod_names_to_delete - pod_names_already_deleted
        remaining_replicasets = (
                replica_set_names - replica_set_names_to_delete - replica_set_names_already_deleted
        )

        if len(remaining_pods) == 0 and len(remaining_replicasets) == 0:
            namespace_to_delete = [current_namespace]

    return namespace_to_delete, replica_sets_to_delete, pods_to_delete, jobs_to_delete


def log_cleanup_changes(
    build, namespace, replica_sets, pods, jobs,
    message='Executing changes:',
    name_formatter=lambda name: name,
):
    with build.stage(message):
        log_actions(build, 'DELETE', 'replica_set', replica_sets, name_formatter)
        log_actions(build, 'DELETE', 'jobs', jobs, name_formatter)
        log_actions(build, 'DELETE', 'pod', pods, name_formatter)
        log_actions(build, 'DELETE', 'namespace', namespace, name_formatter)


def execute_cleanup(build, namespace, replica_sets, pods, jobs):
    with build.stage('Delete replica sets'):
        delete_objects(build, replica_sets, delete_replica_set)

    with build.stage('Delete jobs'):
        delete_objects(build, jobs, delete_job)

    with build.stage('Delete pods'):
        delete_objects(build, pods, delete_pod)

    with build.stage('Delete namespace'):
        delete_objects(build, namespace, delete_namespace)
