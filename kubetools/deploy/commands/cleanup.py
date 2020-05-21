from kubetools.deploy.util import delete_objects, log_actions
from kubetools.kubernetes.api import (
    delete_pod,
    delete_replica_set,
    get_object_name,
    is_kubetools_object,
    list_pods,
    list_replica_sets,
)


# Cleanup
# Handles removal of orphaned replicasets and pods as well as any complete jobs,
# working on the namespace level only (no apps).

def get_cleanup_objects(build):
    replica_sets = list_replica_sets(build.env, build.namespace)
    replica_sets_to_delete = []
    replica_set_names_to_delete = set()

    for replica_set in replica_sets:
        if not is_kubetools_object(replica_set):
            continue

        if not replica_set.metadata.owner_references:
            replica_set_names_to_delete.add(get_object_name(replica_set))
            replica_sets_to_delete.append(replica_set)

    pods = list_pods(build.env, build.namespace)
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
        log_actions(build, 'DELETE', 'replica_set', replica_sets, name_formatter)
        log_actions(build, 'DELETE', 'pod', pods, name_formatter)


def execute_cleanup(build, replica_sets, pods):
    with build.stage('Delete replica sets'):
        delete_objects(build, replica_sets, delete_replica_set)

    with build.stage('Delete pods'):
        delete_objects(build, pods, delete_pod)
