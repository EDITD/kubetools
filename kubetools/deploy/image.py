import requests

from kubetools.exceptions import KubeBuildError
from kubetools.kubernetes.config import make_context_name

from .util import run_shell_command


def get_commit_hash_tag(context_name, commit_hash):
    '''
    Turn a commit hash into a Docker registry tag.
    '''

    return '-'.join((context_name, 'commit', commit_hash))


def get_docker_name(registry, app_name):
    return '{0}/{1}'.format(registry, app_name)


def get_docker_tag(registry, app_name, tag):
    # Tag the image like registry/app:tag
    docker_version = '{0}:{1}'.format(app_name, tag)
    # The full docker tag
    return '{0}/{1}'.format(registry, docker_version)


def get_docker_tag_for_commit(registry, app_name, context_name, commit_hash):
    return get_docker_tag(registry, app_name, get_commit_hash_tag(context_name, commit_hash))


def has_app_commit_image(registry, app_name, context_name, commit_hash):
    '''
    Check the registry has an app image for a certain commit hash.
    '''

    if registry is None:
        raise KubeBuildError(f'Invalid registry to build {context_name}: {registry}')

    commit_version = get_commit_hash_tag(context_name, commit_hash)
    url = 'http://{0}/v2/{1}/manifests/{2}'.format(registry, app_name, commit_version)

    response = requests.head(url)

    if response.status_code != 200:
        return False

    return True


def _get_container_contexts_from_config(app_config):
    context_name_to_build = {}
    container_contexts = app_config.get('containerContexts', {})
    for deployment, data in app_config.get('deployments', {}).items():
        containers = data.get('containers')
        for name, container in containers.items():
            if 'containerContext' in container:
                context_name = container['containerContext']
                if context_name not in container_contexts:
                    raise KubeBuildError(f'{context_name} is not a valid container context')
                container_context = container_contexts[context_name]
                if 'build' in container_context:
                    context_name_to_build[context_name] = container_context['build']

            elif 'build' in container:
                context_name = make_context_name(deployment, name)
                if context_name in context_name_to_build:
                    raise KubeBuildError('Duplicate deployment/container')

                context_name_to_build[context_name] = container['build']

    return context_name_to_build


def ensure_docker_images(kubetools_config, build, *args, **kwargs):
    '''
    Ensures that our Docker registry has the specified image. If not we build
    and upload to the registry.
    '''

    project_name = kubetools_config['name']
    commit_hash = kwargs.get('commit_hash')

    with build.stage(f'Ensuring Docker images built for {project_name}={commit_hash}'):
        return _ensure_docker_images(kubetools_config, build, *args, **kwargs)


def _ensure_docker_images(
    kubetools_config, build, app_dir, commit_hash,
    default_registry=None,
    check_build_control=lambda build: None,
    additional_tags=None,
):
    if additional_tags is None:
        additional_tags = []
    project_name = kubetools_config['name']

    context_name_to_build = _get_container_contexts_from_config(kubetools_config)
    context_name_to_registry = {
        context_name: build_context.get('registry', default_registry)
        for context_name, build_context in context_name_to_build.items()
    }
    build_context_keys = list(context_name_to_build.keys())

    # Check if the image already exists in the registry
    if not build_context_keys or all(
        has_app_commit_image(
            context_name_to_registry[context_name],
            project_name,
            context_name,
            commit_hash,
        )
        for context_name in build_context_keys
    ):
        build.log_info((
            f'All Docker images for {project_name} commit {commit_hash} exists, '
            'skipping build'
        ))

        context_images = {
            # Build the context name -> image dict
            context_name: get_docker_tag_for_commit(
                context_name_to_registry[context_name],
                project_name,
                context_name,
                commit_hash,
            )
            for context_name in build_context_keys
        }

        return context_images

    # We're building something - let's find the previous commit we built
    commit_history = run_shell_command(
        'git', 'log', '--pretty=format:"%h"',
        cwd=app_dir,
    ).decode()

    commit_history = [
        commit.strip('"')
        for commit in commit_history.split()
    ]

    # Figure out the previous commit we built an image for
    previous_commit = None
    first_build_context = build_context_keys[0]
    first_build_registry = context_name_to_registry[first_build_context]
    for i, commit in enumerate(commit_history):
        if has_app_commit_image(
            first_build_registry,
            project_name,
            first_build_context,
            commit,
        ):
            previous_commit = commit
            break

        # We only search the most recent 100 commits before giving up, so as not
        # to overload the registry server.
        elif i >= 100:
            break

    # Check/abort as requested
    check_build_control(build)

    build.log_info(f'Building {project_name} @ commit {commit_hash}')

    # Now actually build the images
    context_images = {}

    for context_name, build_context in context_name_to_build.items():
        # Check/abort as requested
        check_build_control(build)

        registry = build_context.get('registry', default_registry)

        # Run pre docker commands?
        pre_build_commands = build_context.get('preBuildCommands', [])

        for command in pre_build_commands:
            # Check/abort as requested
            check_build_control(build)

            build.log_info(f'Executing pre-build command: {command}')

            # Run it, passing in the commit hashes as ENVars
            env = {
                'KUBE_ENV': build.env,
                'BUILD_COMMIT': commit_hash,
            }
            if previous_commit:
                env['PREVIOUS_BUILD_COMMIT'] = previous_commit

            run_shell_command(*command, cwd=app_dir, env=env)

        # The full docker tag
        docker_tag_for_commit = get_docker_tag_for_commit(
            registry,
            project_name,
            context_name,
            commit_hash,
        )
        additional_docker_tags = [
            get_docker_tag(registry, project_name, additional_tag)
            for additional_tag in additional_tags
        ]
        docker_tags = [docker_tag_for_commit]
        docker_tags.extend(additional_docker_tags)
        tag_arguments = []
        for docker_tag in docker_tags:
            tag_arguments.extend(['-t', docker_tag])

        # Build the image
        build.log_info((
            f'Building {project_name}/{context_name} '
            f'(file: {build_context["dockerfile"]}, commit: {commit_hash})'
        ))

        run_shell_command(
            'docker', 'build', '--pull',
            '-f', build_context['dockerfile'],
            *tag_arguments,
            '.',
            cwd=app_dir,
        )

        # Push the image and additional tags
        for docker_tag in docker_tags:
            build.log_info(f'Pushing docker image: {docker_tag}')
            run_shell_command('docker', 'push', docker_tag)

        context_images[context_name] = docker_tag_for_commit

    return context_images
