import subprocess

import requests

from kubetools.exceptions import KubeBuildError
from kubetools.kubernetes.config import make_context_name
from kubetools.settings import get_settings

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

    settings = get_settings()
    if settings.REGISTRY_CHECK_SCRIPT:
        # We have a REGISTRY_CHECK_SCRIPT config, so use it to check for an image
        cmd = [settings.REGISTRY_CHECK_SCRIPT, registry, app_name, commit_version]
        rc = subprocess.call(cmd)
        if rc == 0:
            # A return code of 0 means the image was found
            return True
        elif rc == 1:
            # A return code of 1 means the image was not found
            return False
        elif rc == 2:
            # A return code of 2 means that the image should be checked using http
            pass
        else:
            # Any other return code means an error occured and we should not continue
            raise Exception('Error checking app image status')

    url = 'http://{0}/v2/{1}/manifests/{2}'.format(registry, app_name, commit_version)

    response = requests.head(url)

    if response.status_code != 200:
        return False

    return True


def get_container_contexts_from_config(app_config):
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
    additional_tags=None,
    build_args=None,
):
    if additional_tags is None:
        additional_tags = []
    if build_args is None:
        build_args = []

    project_name = kubetools_config['name']

    context_name_to_build = get_container_contexts_from_config(kubetools_config)

    build_inputs = {}
    for context_name, build_context in context_name_to_build.items():
        registry = build_context.get('registry', default_registry)

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

        build_inputs[context_name] = {
            'context': build_context,
            'registry': registry,
            'image': docker_tag_for_commit,
            'tags': docker_tags,
        }

    first_context, first_build_input = list(build_inputs.items())[0]
    first_registry = first_build_input["registry"]
    previous_commit = _find_last_pushed_commit(app_dir, first_context, first_registry, project_name)

    build.log_info(f'Building {project_name} @ commit {commit_hash}')

    # Now actually build the images
    for context_name, build_input in build_inputs.items():
        if has_app_commit_image(
            build_input['registry'],
            project_name,
            context_name,
            commit_hash,
        ):
            build.log_info((
                f'Docker image for {project_name}/{context_name} commit {commit_hash} exists, '
                'skipping build'
            ))
            continue

        build_context = build_input['context']

        # Run pre docker commands?
        pre_build_commands = build_context.get('preBuildCommands', [])

        for command in pre_build_commands:
            build.log_info(f'Executing pre-build command: {command}')

            # Run it, passing in the commit hashes as ENVars
            env = {
                'KUBE_ENV': build.env,
                'BUILD_COMMIT': commit_hash,
            }
            if previous_commit:
                env['PREVIOUS_BUILD_COMMIT'] = previous_commit

            run_shell_command(*command, cwd=app_dir, env=env)

        tag_arguments = []
        for docker_tag in build_input['tags']:
            tag_arguments.extend(['-t', docker_tag])

        build_arg_arguments = []
        for build_arg in build_args:
            build_arg_arguments.extend(['--build-arg', build_arg])

        # Build the image
        build.log_info((
            f'Building {project_name}/{context_name} '
            f'(file: {build_context["dockerfile"]}, commit: {commit_hash})'
        ))

        run_shell_command(
            'docker', 'build', '--pull',
            '-f', build_context['dockerfile'],
            *tag_arguments,
            *build_arg_arguments,
            '.',
            cwd=app_dir,
        )

        # Push the image and additional tags
        for docker_tag in build_input['tags']:
            build.log_info(f'Pushing docker image: {docker_tag}')
            run_shell_command('docker', 'push', docker_tag)

    return {
        context_name: build_input['image']
        for context_name, build_input in build_inputs.items()
    }


def _find_last_pushed_commit(app_dir, context_name, registry, project_name, max_commits=100):
    commit_history = run_shell_command(
        'git', 'log', '--pretty=format:"%h"', '--max-count', str(max_commits),
        cwd=app_dir,
    ).decode()

    commit_history = [
        commit.strip('"')
        for commit in commit_history.split()
    ]

    for i, commit in enumerate(commit_history):
        if has_app_commit_image(
                registry,
                project_name,
                context_name,
                commit,
        ):
            return commit
    else:
        return None
