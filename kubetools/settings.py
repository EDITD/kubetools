from configparser import ConfigParser
from functools import lru_cache
from os import access, environ, listdir, path, X_OK

import click

from .log import logger


class KubetoolsSettings(object):
    DEFAULT_KUBE_ENV = 'staging'  # default environment when speaking to the server

    DEV_DEFAULT_ENV = 'dev'  # default environment name in dev
    DEV_HOST = 'localhost'  # dev host to link people to (should map to 127.0.0.1)
    DEV_CONFIG_DIRNAME = '.kubetools'  # project directroy to generate compose config
    DEV_BACKEND = 'docker_compose'  # backend to use for development

    CRONJOBS_BATCH_API_VERSION = 'batch/v1'  # if k8s version < 1.21+ should be 'batch/v1beta1'

    REGISTRY_CHECK_SCRIPT = None
    ''' Optional external script to check if an image exists in the docker registry.

    For cases when the registry cannot be checked by just using the docker registry V2 API.

    The script will be passed 3 arguments:
    * the registry IP/hostname and port (in the form `<ip_or_hostname>:<port>`)
    * the image name, which comes from the app name
    * the image tag (version), which comes from the build context and commit hash
    Concretely they could be used in `docker pull <registry>/<image_name>:<image_tag>`

    The script must return one of the following codes:
    * 0: the image was found in the registry
    * 1: the image was not found in the registry
    * 2: the image should be checked with the HTTP Docker V2 API
    * anything else: the script ran into an error and `kubetools` must abort
    Note that return code 2 is useful for example if the script is only responsible for checking
    some combination of registries or images, but not all.
    '''

    WAIT_SLEEP_TIME = 3
    WAIT_MAX_TIME = int(environ.get('KUBETOOLS_WAIT_MAX_TIME', 300))
    WAIT_MAX_SLEEPS = WAIT_MAX_TIME / WAIT_SLEEP_TIME

    def __init__(self, filename=None):
        self.filename = filename
        self.scripts = []


def get_settings_directory():
    return click.get_app_dir('kubetools', force_posix=True)


@lru_cache(maxsize=1)
def get_settings():
    settings_directory = get_settings_directory()
    settings_file = path.join(settings_directory, 'kubetools.conf')

    settings = KubetoolsSettings(filename=settings_file)

    if path.exists(settings_file):
        logger.info('Loading settings file: {0}'.format(settings_file))
        parser = ConfigParser()
        parser.read(settings_file)

        for option in parser.options('kubetools'):
            setattr(
                settings,
                option.upper().replace('-', '_'),
                parser.get('kubetools', option),
            )

    else:
        logger.info('No settings file: {0}'.format(settings_file))

    scripts_directory = path.join(settings_directory, 'scripts')
    if path.exists(scripts_directory):
        for filename in listdir(scripts_directory):
            if access(path.join(scripts_directory, filename), X_OK):
                settings.scripts.append(filename)

    return settings
