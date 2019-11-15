import six

from kubetools_client.exceptions import KubeConfigError

from .deployment import make_deployment_config
from .job import make_job_config
from .service import make_service_config
from .util import copy_and_update


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

    for container_name, data in six.iteritems(containers):
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
    deployment_labels=None,  # deployment-only extra labels
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

    base_annotations = base_annotations or {}
    per_deployment_annotations = per_deployment_annotations or {}

    job_specs = job_specs or []

    main_services = []
    main_deployments = []

    for name, deployment in six.iteritems(config.get('deployments', {})):
        # This is expected - kubetools.yml deployments need not prefix names
        # with the project name.
        if not name.startswith(project_name):
            deployment_name = '-'.join((project_name, name))
        # Originally the deployment name was used as-is, ie <app>-<deployment>,
        # so we want to avoid breaking those.
        else:
            deployment_name = name

        app_labels = copy_and_update(
            base_labels,
            deployment_labels,
            {
                'role': 'app',
                'name': deployment_name,
            },
        )

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
            main_services.append(make_service_config(
                deployment_name,
                container_ports,
                labels=app_labels,
                annotations=app_annotations,
            ))

        # Setup top level app deployment
        deployment_replicas = replicas

        if 'maxReplicas' in deployment:
            deployment_replicas = min(deployment_replicas, deployment['maxReplicas'])

        main_deployments.append(make_deployment_config(
            deployment_name,
            containers,
            replicas=deployment_replicas,
            labels=app_labels,
            annotations=app_annotations,
            envvars=envvars,
        ))

    # Handle dependencies
    depend_services = []
    depend_deployments = []

    for name, dependency in six.iteritems(config.get('dependencies', {})):
        dependency_name = '-'.join((project_name, name))
        dependency_labels = copy_and_update(base_labels, {
            'role': 'dependency',
            'name': dependency_name,
        })

        containers, container_ports = _get_containers_data(
            dependency['containers'],
            context_name_to_image=context_name_to_image,
            deployment_name=name,
        )
        app_annotations = copy_and_update(base_annotations)

        if container_ports:
            depend_services.append(make_service_config(
                dependency_name,
                container_ports,
                labels=dependency_labels,
                annotations=app_annotations,
            ))

        # For now, all dependencies use one replica
        depend_deployments.append(make_deployment_config(
            dependency_name,
            containers,
            labels=dependency_labels,
            annotations=app_annotations,
            envvars=envvars,
        ))

    # Correctly order the configs, such that dependencies build first:
    # dependencies -> main apps -> singletons
    services = depend_services

    # This might not exist if we're a port-less app
    if main_services:
        services.extend(main_services)

    deployments = depend_deployments + main_deployments

    # Jobs can be upgrades and/or passed in as part of the build spec
    jobs = []
    job_labels = copy_and_update(base_labels, {
        'role': 'job',
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
            for name, data in six.iteritems(config.get('deployments')):
                found_image = False

                for _, container in six.iteritems(data['containers']):
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
