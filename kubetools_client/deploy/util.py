import os

from subprocess import CalledProcessError, check_output, STDOUT

from kubernetes import client, config

from kubetools_client.exceptions import KubeBuildError
from kubetools_client.log import logger


def run_shell_command(*command, **kwargs):
    '''
    Run a shell command and return it's output. Capture fails and pass to internal
    exception.
    '''

    cwd = kwargs.pop('cwd', None)
    env = kwargs.pop('env', {})

    new_env = os.environ.copy()
    new_env.update(env)

    logger.debug(f'Running shell command in {cwd}: {command}, env: {env}')

    try:
        return check_output(command, stderr=STDOUT, cwd=cwd, env=new_env)

    except CalledProcessError as e:
        raise KubeBuildError('Command failed: {0}\n\n{1}'.format(
            ' '.join(command),
            e.output.decode('utf-8', 'ignore'),
        ))


def _get_api_client(build):
    return config.new_client_from_config(context=build.env)


def get_k8s_core_api(build):
    api_client = _get_api_client(build)
    return client.CoreV1Api(api_client=api_client)


def get_k8s_apps_api(build):
    api_client = _get_api_client(build)
    return client.AppsV1beta1Api(api_client=api_client)


def get_k8s_batch_api(build):
    api_client = _get_api_client(build)
    return client.BatchV1Api(api_client=api_client)
