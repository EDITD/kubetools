import sys

from kubetools.settings import get_settings

from . import docker_compose


DEV_BACKEND_PROVIDERS = {
    'docker_compose': docker_compose,
}


# Now, using settings splice in the .backend module to match the provider
settings = get_settings()

try:
    backend = DEV_BACKEND_PROVIDERS[settings.DEV_BACKEND]
except KeyError:
    raise KeyError('Invalid dev backend: {0}'.format(settings.DEV_BACKEND))

sys.modules['kubetools.dev.backend'] = backend
backend.init_backend()
