import six

from kubetools_client.exceptions import KubeConfigError
from kubetools_client.log import logger

from .deployment import make_deployment_config
from .job import make_job_config
from .service import make_service_config
from .util import copy_and_update

DEFAULT_VERSION = 'develop'
DEFAULT_KUBE_ENV = 'staging'


def get_commit_hash_tag(context_name, commit_hash):
    '''
    Turn a commit hash into a Docker registry tag.
    '''

    return '-'.join((context_name, 'commit', commit_hash))


def _get_docker_tag(registry, app_name, context_name, commit_hash):
    # Tag the image like registry/app:commit-hash
    docker_version = '{0}:{1}'.format(
        app_name,
        get_commit_hash_tag(context_name, commit_hash),
    )

    # The full docker tag
    return '{0}/{1}'.format(registry, docker_version)


def _make_context_name(app_name, container_name):
    return f'{app_name}-{container_name}'


def _ensure_image(
    obj, registry, project_name, commit_hash,
    app_name=None, container_name=None,
):
    if 'image' in obj:
        return

    if 'containerContext' in obj:
        obj['image'] = _get_docker_tag(
            registry,
            project_name,
            obj.pop('containerContext'),
            commit_hash,
        )

    elif 'build' in obj and app_name and container_name:
        # Because no shared context was provided we use the deployment + container name
        context_name = _make_context_name(app_name, container_name)
        obj['image'] = _get_docker_tag(
            registry,
            project_name,
            context_name,
            commit_hash,
        )

    else:
        raise KubeConfigError('No image for container: {0}'.format(obj))


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


def _get_container_data(
    containers, registry, project_name, app_name, commit_hash, kube_env, namespace,
    get_app_host_for_env=None,
):
    # Setup top level app service mapping all ports from all top level containers
    all_container_ports = []
    all_containers = {}

    for container_name, data in six.iteritems(containers):
        all_container_ports.extend(data.get('ports', []))
        _ensure_image(
            data, registry, project_name, commit_hash,
            app_name=app_name, container_name=container_name,
        )
        all_containers[container_name] = data

    extra_annotations = {}

    # Create the special `kubetools/dns_name` annotation where we are planning
    # to expose this service. This is used by external routers/similar to route
    # the domain -> the nodePort.
    if get_app_host_for_env and _should_expose_ports(all_container_ports):
        extra_annotations['kubetools/dns_name'] = get_app_host_for_env(
            kube_env, namespace, app_name,
        )

    return all_containers, all_container_ports, extra_annotations


def generate_kubernetes_configs(
    source_name, config,
    version=DEFAULT_VERSION, replicas=1, commit_hash=None,
    kube_env=DEFAULT_KUBE_ENV, namespace=None, job_specs=None,
    envars=None, annotations=None, include_upgrades=True,
    is_manifest=False, registry=None, get_app_host_for_env=None,
):
    '''
    Builds service & deployment definitions based on the app config provided. We have
    app configs for each of our Kubernetes-ready apps, and they specify the basic spec
    minus things we want to change via Kubetools (replicas, versions).

    Returns two ordered lists (service configs, deployment configs). The builder executes
    them in-order, starting with the services. This means we can start dependencies before
    the main apps, so they lookup the correct settings.
    '''

    logger.debug((
        'Building Kubernetes objects for {0} '
        '(version={version}, replicas={replicas}, commit={commit_hash})'
    ).format(
        source_name,
        version=version,
        replicas=replicas,
        commit_hash=commit_hash,
    ))

    base_annotations = annotations or {}
    job_specs = job_specs or []

    base_annotations.update({
        'kube_env': kube_env,
        # Version is the branch name, which may contain chars that don't work on
        # Kubernetes labels, so it's an annotation.
        'version': version,
    })

    project_name = config['name']

    # All Kubernetes services/deployments/jobs will use this base selectors
    base_labels = {
        'project_name': project_name,
        'project_source_name': source_name,  # this is the name used to create these apps
        'project_source_type': 'manifest' if is_manifest else 'git',
    }

    if is_manifest:
        base_labels['manifest_name'] = source_name
    else:
        base_labels['git_name'] = source_name

    container_kwargs = {
        'kube_env': kube_env,
        'namespace': namespace,
        'envars': envars,
    }

    main_services = []
    main_deployments = []

    for name, deployment in six.iteritems(config.get('deployments', {})):
        app_labels = copy_and_update(base_labels, {
            'role': 'app',
            'name': name,
        })

        # Sometimes (manifests) we don't have a commit available - note we also
        # only apply this to app deployments, not dependencies.
        if commit_hash:
            app_labels['git_commit'] = commit_hash

        containers, container_ports, extra_annotations = _get_container_data(
            deployment['containers'],
            registry=registry,
            project_name=project_name,
            app_name=name,
            commit_hash=commit_hash,
            kube_env=kube_env,
            namespace=namespace,
            get_app_host_for_env=get_app_host_for_env,
        )
        app_annotations = copy_and_update(base_annotations, extra_annotations)

        if container_ports:
            main_services.append(make_service_config(
                name,
                container_ports,
                labels=app_labels,
                annotations=app_annotations,
            ))

        # Setup top level app deployment
        deployment_replicas = replicas

        if 'maxReplicas' in deployment:
            deployment_replicas = min(deployment_replicas, deployment['maxReplicas'])

        main_deployments.append(make_deployment_config(
            name,
            containers,
            replicas=deployment_replicas,
            labels=app_labels,
            version=version,
            annotations=app_annotations,
            **container_kwargs
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

        containers, container_ports, extra_annotations = _get_container_data(
            dependency['containers'],
            registry=registry,
            project_name=project_name,
            app_name=dependency_name,
            commit_hash=commit_hash,
            kube_env=kube_env,
            namespace=namespace,
        )
        app_annotations = copy_and_update(base_annotations, extra_annotations)

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
            **container_kwargs
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
    if include_upgrades:
        for job_spec in config.get('upgrades', {}):
            _ensure_image(job_spec, registry, project_name, commit_hash)

            jobs.append(make_job_config(
                job_spec,
                app_name=project_name,
                labels=job_labels,
                annotations=base_annotations,
                **container_kwargs
            ))

    # Jobs can provide their own envars
    job_base_envars = container_kwargs.pop('envars', {})

    for job_spec in job_specs:
        # We already have a containerContext? Let's make that an image
        if 'containerContext' in job_spec:
            job_spec['image'] = _get_docker_tag(
                registry,
                project_name,
                job_spec.pop('containerContext'),
                commit_hash,
            )

        # Stil no image? Let's pull the first container we have available - this
        # maintains backwards compatability where one can ask for a job without
        # specifying any container (back when every app was one container).
        if 'image' not in job_spec:
            for name, data in six.iteritems(config.get('deployments')):
                found_context = False

                for _, container in six.iteritems(data['containers']):
                    if 'containerContext' in container:
                        job_spec['image'] = _get_docker_tag(
                            registry,
                            project_name,
                            container['containerContext'],
                            commit_hash,
                        )
                        found_context = True
                        break

                if found_context:
                    break

            # We did not break - no context found!
            else:
                raise KubeConfigError((
                    'Could not find a containerContext to use for job: {0}'
                ).format(job_spec))

        job_envars = copy_and_update(job_base_envars, job_spec.get('envars', {}))

        jobs.append(make_job_config(
            job_spec,
            app_name=project_name,
            labels=job_labels,
            annotations=base_annotations,
            envars=job_envars,
            **container_kwargs
        ))

    return services, deployments, jobs
