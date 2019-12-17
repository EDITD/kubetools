import os

from subprocess import CalledProcessError, check_output, STDOUT

from kubetools.exceptions import KubeBuildError
from kubetools.log import logger


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
