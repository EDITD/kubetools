from kubetools.constants import (
    MANAGED_BY_ANNOTATION_KEY,
    NAME_LABEL_KEY,
    PROJECT_NAME_LABEL_KEY,
    ROLE_LABEL_KEY,
)
from kubetools.exceptions import KubeConfigError

from .cronjob import make_cronjob_config
from .deployment import make_deployment_config
from .job import make_job_config
from .namespace import make_namespace_config
from .service import make_service_config
from .util import copy_and_update


def make_deployment_name(project_name, deployment_name):
    project_name = project_name.replace('_', '-')
    deployment_name = deployment_name.replace('_', '-')

    if deployment_name.startswith(project_name):
        return deployment_name

    # We expect to come here - but some old kubetools.yml's will prefix
    # the project name before every deployment.
    return '-'.join((project_name, deployment_name))


def make_context_name(app_name, container_name):
    return '{0}-{1}'.format(app_name, container_name)


def _ensure_image(
    container, context_name_to_image,
    deployment_name=None,
    container_name=None,
    default_registry=None,
):
    if 'image' in container:
        return

    if 'containerContext' in container:
        context_name = container.pop('containerContext')
        container.pop('build', None)

    elif 'build' in container and deployment_name and container_name:
        # Because no shared context was provided we use the deployment + container name
        context_name = make_context_name(deployment_name, container_name)
        container.pop('build')
    else:
        raise KubeConfigError('No image for container: {0}'.format(container))

    container['image'] = context_name_to_image[context_name]

    registry_image = container['image'].split('/')
    if len(registry_image) == 1 and default_registry is not None:
        # If registry is not specified but a default was provided
        container['image'] = f'{default_registry}/{container["image"]}'


def _get_containers_data(
    containers,
    context_name_to_image,
    deployment_name,
    default_registry=None,
):
    # Setup top level app service mapping all ports from all top level containers
    all_container_ports = []
    all_containers = {}

    for container_name, data in containers.items():
        all_container_ports.extend(data.pop('ports', []))
        _ensure_image(
            data, context_name_to_image,
            deployment_name, container_name,
            default_registry=default_registry,
        )
        all_containers[container_name] = data

    return all_containers, all_container_ports


def _get_replicas(deployment, default=1):
    replicas = default

    if 'replicaMultiplier' in deployment:
        replicas = replicas * deployment['replicaMultiplier']

    if 'maxReplicas' in deployment:
        replicas = min(replicas, deployment['maxReplicas'])

    if 'minReplicas' in deployment:
        replicas = max(replicas, deployment['minReplicas'])

    return replicas


def generate_namespace_config(name, base_labels=None, base_annotations=None):
    base_annotations = copy_and_update(base_annotations, {
        MANAGED_BY_ANNOTATION_KEY: 'kubetools',
    })

    base_labels = copy_and_update(base_labels, {
        PROJECT_NAME_LABEL_KEY: name,
    })

    namespace = make_namespace_config(
        name,
        labels=base_labels,
        annotations=base_annotations,
    )

    return namespace


def generate_kubernetes_configs_for_project(
    config,  # a kubetools config object
    replicas=1,  # number of replicas for each deployment
    envvars=None,  # global environment variables to inject to all containers

    # Upgrades/jobs
    include_upgrade_jobs=True,  # whether to generate jobs for config.upgrades
    job_specs=None,  # additional job configs to execute

    # Labels/annotations
    base_labels=None,
    base_annotations=None,
    per_deployment_annotations=None,  # per-deployment extra annotations

    # Map of context name -> docker image - images are expected to be built by
    # something else (normally the kubetools server or ktd client).
    context_name_to_image=None,
    default_registry=None,
):
    '''
    Builds service & deployment definitions based on the app config provided. We have
    app configs for each of our Kubernetes-ready apps, and they specify the basic spec
    minus things we want to change via Kubetools (replicas, versions).

    Returns two ordered lists (service configs, deployment configs). The builder executes
    them in-order, starting with the services. This means we can start dependencies before
    the main apps, so they lookup the correct settings.
    '''

    project_name = config['name']

    base_labels = copy_and_update(base_labels, {
        PROJECT_NAME_LABEL_KEY: project_name,
    })

    base_annotations = copy_and_update(base_annotations, {
        MANAGED_BY_ANNOTATION_KEY: 'kubetools',
    })

    envvars = copy_and_update(envvars, {
        'KUBE': 'true',
    })

    base_annotations = base_annotations or {}
    per_deployment_annotations = per_deployment_annotations or {}

    job_specs = job_specs or []

    services = []
    deployments = []

    for name, dependency in config.get('dependencies', {}).items():
        dependency_name = make_deployment_name(project_name, name)
        dependency_labels = copy_and_update(base_labels, {
            ROLE_LABEL_KEY: 'dependency',
            NAME_LABEL_KEY: dependency_name,
        })

        node_selector_labels = dependency.get('nodeSelector', None)
        service_account_name = dependency.get('serviceAccountName', None)
        secrets = dependency.get('secrets', None)

        containers, container_ports = _get_containers_data(
            dependency['containers'],
            context_name_to_image=context_name_to_image,
            deployment_name=name,
            default_registry=default_registry,
        )
        app_annotations = copy_and_update(base_annotations)

        if container_ports:
            services.append(make_service_config(
                dependency_name,
                container_ports,
                labels=dependency_labels,
                annotations=app_annotations,
            ))

        # For now, all dependencies use one replica
        deployments.append(make_deployment_config(
            dependency_name,
            containers,
            replicas=1,
            labels=dependency_labels,
            annotations=app_annotations,
            envvars=envvars,
            update_strategy=dependency.get('updateStrategy'),
            node_selector_labels=node_selector_labels,
            service_account_name=service_account_name,
            secrets=secrets,
        ))

    for name, deployment in config.get('deployments', {}).items():
        deployment_name = make_deployment_name(project_name, name)
        deployment_labels = copy_and_update(base_labels, {
            ROLE_LABEL_KEY: 'app',
            NAME_LABEL_KEY: deployment_name,
        })

        node_selector_labels = deployment.get('nodeSelector', None)
        service_account_name = deployment.get('serviceAccountName', None)
        secrets = deployment.get('secrets', None)

        containers, container_ports = _get_containers_data(
            deployment['containers'],
            context_name_to_image=context_name_to_image,
            deployment_name=name,
            default_registry=default_registry,
        )
        app_annotations = copy_and_update(
            base_annotations,
            per_deployment_annotations.get(name),
        )

        if container_ports:
            services.append(make_service_config(
                deployment_name,
                container_ports,
                labels=deployment_labels,
                annotations=app_annotations,
            ))

        # Setup top level app deployment
        deployment_replicas = _get_replicas(deployment, default=replicas)
        deployments.append(make_deployment_config(
            deployment_name,
            containers,
            replicas=deployment_replicas,
            labels=deployment_labels,
            annotations=app_annotations,
            envvars=envvars,
            update_strategy=deployment.get('updateStrategy'),
            node_selector_labels=node_selector_labels,
            service_account_name=service_account_name,
            secrets=secrets,
        ))

    # Jobs can be upgrades and/or passed in as part of the build spec
    jobs = []
    job_labels = copy_and_update(base_labels, {
        ROLE_LABEL_KEY: 'job',
    })

    # Add any upgrade jobs
    if include_upgrade_jobs:
        job_specs = config.get('upgrades', []) + job_specs

    for job_spec in job_specs:
        _ensure_image(job_spec, context_name_to_image, default_registry=default_registry)

        # Stil no image? Let's pull the first container we have available - this
        # maintains backwards compatability where one can ask for a job without
        # specifying any container (back when every app was one container).
        if 'image' not in job_spec:
            for name, data in config.get('deployments').items():
                found_image = False

                for _, container in data['containers'].items():
                    if 'image' in container:
                        job_spec['image'] = container['image']
                        found_image = True
                        break

                if found_image:
                    break

            # We did not break - no context found!
            else:
                raise KubeConfigError((
                    'Could not find a containerContext to use for job: {0}'
                ).format(job_spec))

        job_envvars = copy_and_update(
            envvars,
            job_spec.get('envars'),  # legacy support TODO: remove!
            job_spec.get('envvars'),
        )

        node_selector_labels = job_spec.get('nodeSelector', None)
        service_account_name = job_spec.get('serviceAccountName', None)
        secrets = job_spec.get('secrets', None)

        jobs.append(make_job_config(
            job_spec,
            app_name=project_name,
            labels=job_labels,
            annotations=base_annotations,
            envvars=job_envvars,
            node_selector_labels=node_selector_labels,
            service_account_name=service_account_name,
            secrets=secrets,
        ))

    cronjobs = []

    for name, cronjob in config.get('cronjobs', {}).items():
        cronjob_labels = copy_and_update(base_labels, {
            ROLE_LABEL_KEY: 'cronjob',
            NAME_LABEL_KEY: name,
        })

        node_selector_labels = cronjob.get('nodeSelector', None)
        service_account_name = cronjob.get('serviceAccountName', None)
        secrets = cronjob.get('secrets', None)

        containers, container_ports = _get_containers_data(
            cronjob['containers'],
            context_name_to_image=context_name_to_image,
            deployment_name=name,
            default_registry=default_registry,
        )

        app_annotations = copy_and_update(base_annotations)
        schedule = cronjob['schedule']
        concurrency_policy = cronjob['concurrency_policy']
        batch_api_version = cronjob.get('batch-api-version')  # May depend on target cluster

        cronjobs.append(make_cronjob_config(
            config,
            name,
            schedule,
            batch_api_version,
            concurrency_policy,
            containers,
            labels=cronjob_labels,
            annotations=app_annotations,
            envvars=envvars,
            node_selector_labels=node_selector_labels,
            service_account_name=service_account_name,
            secrets=secrets,
        ))

    return services, deployments, jobs, cronjobs
