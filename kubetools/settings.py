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
