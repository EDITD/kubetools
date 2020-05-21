import os

from subprocess import CalledProcessError, check_output, STDOUT

from kubetools.constants import NAME_LABEL_KEY
from kubetools.exceptions import KubeBuildError
from kubetools.kubernetes.api import get_object_name, is_kubetools_object
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


def log_actions(build, action, object_type, names, name_formatter):
    for name in names:
        if not isinstance(name, str):
            name = get_object_name(name)
        build.log_info(f'{action} {object_type} {name_formatter(name)}')


def delete_objects(build, objects, delete_function):
    for obj in objects:
        delete_function(build, obj)


def get_app_objects(
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
