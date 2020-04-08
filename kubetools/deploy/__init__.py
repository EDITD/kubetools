from collections import defaultdict
from os import path

from kubetools.config import load_kubetools_config
from kubetools.constants import (
    GIT_BRANCH_ANNOTATION_KEY,
    GIT_COMMIT_ANNOTATION_KEY,
    GIT_TAG_ANNOTATION_KEY,
    NAME_LABEL_KEY,
    ROLE_LABEL_KEY,
)
from kubetools.exceptions import KubeBuildError

from .image import ensure_docker_images
from .kubernetes.api import (
    create_deployment,
    create_job,
    create_or_update_deployment,
    create_or_update_service,
    create_service,
    delete_deployment,
    delete_job,
    delete_pod,
    delete_replica_set,
    delete_service,
    deployment_exists,
    get_object_name,
    is_kubetools_object,
    list_deployments,
    list_jobs,
    list_pods,
    list_replica_sets,
    list_services,
    service_exists,
    update_deployment,
    update_service,
    wait_for_deployment,
)
from .kubernetes.config import generate_kubernetes_configs_for_project
from .util import run_shell_command


def _log_actions(build, action, object_type, names, name_formatter):
    for name in names:
        if not isinstance(name, str):
            name = get_object_name(name)
        build.log_info(f'{action} {object_type} {name_formatter(name)}')


def _delete_objects(build, objects, delete_function):
    for obj in objects:
        delete_function(build, obj)


def _get_app_objects(
    build, app_names, list_objects_function,
    force=False,
    check_leftovers=True,
):
    objects = list_objects_function(build)

    def filter_object(obj):
        if not is_kubetools_object(obj):
            if force:
                warning = f'Will touch {get_object_name(obj)} that is not managed by kubetools!'
            else:
                warning = f'Refusing to touch {get_object_name(obj)} as not managed by kubetools!'

            build.log_warning(warning)
            return force is True
        return True

    objects = list(filter(filter_object, objects))

    if app_names:
        objects = list(filter(
            lambda obj: obj.metadata.labels.get(NAME_LABEL_KEY) in app_names,
            objects,
        ))

        if check_leftovers:
            object_names_to_delete = set([
                obj.metadata.labels[NAME_LABEL_KEY]
                for obj in objects
            ])

            leftover_app_names = set(app_names) - object_names_to_delete
            if leftover_app_names:
                raise KubeBuildError(f'{leftover_app_names} not found')

    return objects


def _get_git_info(app_dir):
    git_annotations = {}

    commit_hash = run_shell_command(
        'git', 'rev-parse', '--short=7', 'HEAD',
        cwd=app_dir,
    ).strip().decode()
    git_annotations[GIT_COMMIT_ANNOTATION_KEY] = commit_hash

    branch_name = run_shell_command(
        'git', 'rev-parse', '--abbrev-ref', 'HEAD',
        cwd=app_dir,
    ).strip().decode()

    if branch_name != 'HEAD':
        git_annotations[GIT_BRANCH_ANNOTATION_KEY] = branch_name

    try:
        git_tag = run_shell_command(
            'git', 'tag', '--points-at', commit_hash,
            cwd=app_dir,
        ).strip().decode()
    except KubeBuildError:
        pass
    else:
        if git_tag:
            git_annotations[GIT_TAG_ANNOTATION_KEY] = git_tag

    return commit_hash, git_annotations


# Deploy/upgrade
# Handles deploying new services and upgrading existing ones

def get_deploy_objects(build, app_dirs, replicas=None, default_registry=None):
    all_services = []
    all_deployments = []
    all_jobs = []

    for app_dir in app_dirs:
        envvars = {
            'KUBE_ENV': build.env,
            'KUBE_NAMESPACE': build.namespace,
        }

        annotations = {
            'kubetools/env': build.env,
            'kubetools/namespace': build.namespace,
        }

        if path.exists(path.join(app_dir, '.git')):
            commit_hash, git_annotations = _get_git_info(app_dir)
            annotations.update(git_annotations)
        else:
            raise KubeBuildError(f'{app_dir} is not a valid git repository!')

        kubetools_config = load_kubetools_config(
            app_dir,
            env=build.env,
            namespace=build.namespace,
        )

        context_to_image = ensure_docker_images(
            kubetools_config, build, app_dir,
            commit_hash=commit_hash,
            default_registry=default_registry,
        )

        services, deployments, jobs = generate_kubernetes_configs_for_project(
            kubetools_config,
            envvars=envvars,
            context_name_to_image=context_to_image,
            base_annotations=annotations,
            replicas=replicas or 1,
        )

        all_services.extend(services)
        all_deployments.extend(deployments)
        all_jobs.extend(jobs)

    existing_deployments = {
        get_object_name(deployment): deployment
        for deployment in list_deployments(build)
    }

    # If we haven't been provided an explicit number of replicas, default to using
    # anything that exists live when available.
    if replicas is None:
        for deployment in all_deployments:
            existing_deployment = existing_deployments.get(get_object_name(deployment))
            if existing_deployment:
                deployment['spec']['replicas'] = existing_deployment.spec.replicas

    return all_services, all_deployments, all_jobs


def log_deploy_changes(
    build, services, deployments, jobs,
    message='Executing changes:',
    name_formatter=lambda name: name,
):
    existing_service_names = set(
        get_object_name(service) for service in list_services(build)
    )
    existing_deployment_names = set(
        get_object_name(deployment) for deployment in list_deployments(build)
    )

    deploy_service_names = set(
        get_object_name(service) for service in services
    )
    deploy_deployment_names = set(
        get_object_name(deployment) for deployment in deployments
    )

    new_services = deploy_service_names - existing_service_names
    update_services = deploy_service_names - new_services

    new_deployments = deploy_deployment_names - existing_deployment_names
    update_deployments = deploy_deployment_names - new_deployments

    with build.stage(message):
        _log_actions(build, 'CREATE', 'service', new_services, name_formatter)
        _log_actions(build, 'CREATE', 'deployment', new_deployments, name_formatter)
        _log_actions(build, 'UPDATE', 'service', update_services, name_formatter)
        _log_actions(build, 'UPDATE', 'deployment', update_deployments, name_formatter)


def execute_deploy(build, services, deployments, jobs):
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


# Remove
# Handles removal of deployments, services and jobs in a namespace

def get_remove_objects(build, app_names=None, force=False):
    services_to_delete = _get_app_objects(
        build,
        app_names,
        list_services,
        force=force,
    )
    deployments_to_delete = _get_app_objects(
        build,
        app_names,
        list_deployments,
        force=force,
    )
    jobs_to_delete = _get_app_objects(
        build,
        app_names,
        list_jobs,
        force=force,
        check_leftovers=False,
    )

    return services_to_delete, deployments_to_delete, jobs_to_delete


def log_remove_changes(
    build, services, deployments, jobs,
    message='Executing changes:',
    name_formatter=lambda name: name,
):
    with build.stage(message):
        _log_actions(build, 'DELETE', 'service', services, name_formatter)
        _log_actions(build, 'DELETE', 'deployment', deployments, name_formatter)
        _log_actions(build, 'DELETE', 'job', jobs, name_formatter)


def execute_remove(build, services, deployments, jobs):
    if services:
        with build.stage('Delete services'):
            _delete_objects(build, services, delete_service)

    if deployments:
        with build.stage('Delete deployments'):
            _delete_objects(build, deployments, delete_deployment)

    if jobs:
        with build.stage('Delete jobs'):
            _delete_objects(build, jobs, delete_job)


# Restart
# Handles restarting a deployment by deleting each pod and waiting for recovery

def get_restart_objects(build, app_names=None):
    deployments = _get_app_objects(build, app_names, list_deployments)
    name_to_deployment = {
        get_object_name(deployment): deployment
        for deployment in deployments
    }

    replica_sets = list_replica_sets(build)
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

    pods = list_pods(build)
    deployment_name_to_pods = defaultdict(list)

    for pod in pods:
        if len(pod.metadata.owner_references) == 1:
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
        _log_actions(build, 'RESTART', 'deployment', deployments, name_formatter)


def execute_restart(build, deployments_and_pods):
    for deployment, pods in deployments_and_pods:
        with build.stage(f'Restart pods for {get_object_name(deployment)}'):
            for pod in pods:
                delete_pod(build, pod)
                wait_for_deployment(build, deployment)


# Cleanup
# Handles removal of orphaned replicasets and pods as well as any complete jobs,
# working on the namespace level only (no apps).

def get_cleanup_objects(build):
    replica_sets = list_replica_sets(build)
    replica_sets_to_delete = []
    replica_set_names_to_delete = set()

    for replica_set in replica_sets:
        if not is_kubetools_object(replica_set):
            continue

        if not replica_set.metadata.owner_references:
            replica_set_names_to_delete.add(get_object_name(replica_set))
            replica_sets_to_delete.append(replica_set)

    pods = list_pods(build)
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
        _log_actions(build, 'DELETE', 'replica_set', replica_sets, name_formatter)
        _log_actions(build, 'DELETE', 'pod', pods, name_formatter)


def execute_cleanup(build, replica_sets, pods):
    with build.stage('Delete replica sets'):
        _delete_objects(build, replica_sets, delete_replica_set)

    with build.stage('Delete pods'):
        _delete_objects(build, pods, delete_pod)
