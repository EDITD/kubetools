from collections import defaultdict

from kubetools.deploy.util import get_app_objects, log_actions
from kubetools.kubernetes.api import (
    delete_pod,
    get_object_name,
    list_deployments,
    list_pods,
    list_replica_sets,
    wait_for_deployment,
)


# Restart
# Handles restarting a deployment by deleting each pod and waiting for recovery

def get_restart_objects(build, app_names=None, force=False):
    deployments = get_app_objects(
        build,
        app_names,
        list_deployments,
        force=force,
    )
    name_to_deployment = {
        get_object_name(deployment): deployment
        for deployment in deployments
    }

    replica_sets = list_replica_sets(build.env, build.namespace)
    replica_set_names_to_deployment = {}

    for replica_set in replica_sets:
        if not replica_set.metadata.owner_references:
            build.log_warning((
                'Found replicaSet with no owner (needs cleanup): '
                f'{replica_set.metadata.name}'
            ))
            continue

        if len(replica_set.metadata.owner_references) > 1:
            build.log_error((
                'Found replicaSet with more than one owner: '
                f'{replica_set.metadata.name}'
            ))
            continue

        owner_name = replica_set.metadata.owner_references[0].name
        if owner_name in name_to_deployment:
            replica_set_names_to_deployment[get_object_name(replica_set)] = (
                name_to_deployment[owner_name]
            )

    pods = list_pods(build.env, build.namespace)
    deployment_name_to_pods = defaultdict(list)

    for pod in pods:
        if pod.metadata.owner_references and len(pod.metadata.owner_references) == 1:
            owner = pod.metadata.owner_references[0]
            deployment = replica_set_names_to_deployment.get(owner.name)
            if deployment:
                deployment_name_to_pods[get_object_name(deployment)].append(pod)

    return [
        (name_to_deployment[name], pods)
        for name, pods in deployment_name_to_pods.items()
    ]


def log_restart_changes(
    build, deployments_and_pods,
    message='Executing changes:',
    name_formatter=lambda name: name,
):
    deployments = [deployment for deployment, _ in deployments_and_pods]
    with build.stage(message):
        log_actions(build, 'RESTART', 'deployment', deployments, name_formatter)


def execute_restart(build, deployments_and_pods):
    for deployment, pods in deployments_and_pods:
        with build.stage(f'Restart pods for {get_object_name(deployment)}'):
            for pod in pods:
                build.log_info(f'Delete pod: {get_object_name(pod)}')
                delete_pod(build.env, build.namespace, pod)
                wait_for_deployment(build.env, build.namespace, deployment)
