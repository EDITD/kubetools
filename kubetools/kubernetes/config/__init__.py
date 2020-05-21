from kubetools.constants import (
    MANAGED_BY_ANNOTATION_KEY,
    NAME_LABEL_KEY,
    PROJECT_NAME_LABEL_KEY,
    ROLE_LABEL_KEY,
)
from kubetools.exceptions import KubeConfigError

from .deployment import make_deployment_config
from .job import make_job_config
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
):
    if 'image' in container:
        return

    if 'containerContext' in container:
        context_name = container['containerContext']

    elif 'build' in container and deployment_name and container_name:
        # Because no shared context was provided we use the deployment + container name
        context_name = make_context_name(deployment_name, container_name)
    else:
        raise KubeConfigError('No image for container: {0}'.format(container))

    container['image'] = context_name_to_image[context_name]


def _should_expose_ports(ports):
    for port in ports:
        if port == 80:  # simply HTTP? OK!
            return True

        if not isinstance(port, dict):
            continue

        if (
            port.get('name') == 'http'  # either called http
            or port.get('targetPort', port.get('port')) == 80  # or on port 80
        ):
            return True

    return False


def _get_containers_data(containers, context_name_to_image, deployment_name):
    # Setup top level app service mapping all ports from all top level containers
    all_container_ports = []
    all_containers = {}

    for container_name, data in containers.items():
        all_container_ports.extend(data.get('ports', []))
        _ensure_image(
            data, context_name_to_image,
            deployment_name, container_name,
        )
        all_containers[container_name] = data

    return all_containers, all_container_ports


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

        containers, container_ports = _get_containers_data(
            dependency['containers'],
            context_name_to_image=context_name_to_image,
            deployment_name=name,
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
            labels=dependency_labels,
            annotations=app_annotations,
            envvars=envvars,
            update_strategy=dependency.get('updateStrategy'),
        ))

    for name, deployment in config.get('deployments', {}).items():
        deployment_name = make_deployment_name(project_name, name)
        deployment_labels = copy_and_update(base_labels, {
            ROLE_LABEL_KEY: 'app',
            NAME_LABEL_KEY: deployment_name,
        })

        containers, container_ports = _get_containers_data(
            deployment['containers'],
            context_name_to_image=context_name_to_image,
            deployment_name=name,
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
        deployment_replicas = replicas

        if 'maxReplicas' in deployment:
            deployment_replicas = min(deployment_replicas, deployment['maxReplicas'])

        deployments.append(make_deployment_config(
            deployment_name,
            containers,
            replicas=deployment_replicas,
            labels=deployment_labels,
            annotations=app_annotations,
            envvars=envvars,
            update_strategy=deployment.get('updateStrategy'),
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
        _ensure_image(job_spec, context_name_to_image)

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

        jobs.append(make_job_config(
            job_spec,
            app_name=project_name,
            labels=job_labels,
            annotations=base_annotations,
            envvars=job_envvars,
        ))

    return services, deployments, jobs
