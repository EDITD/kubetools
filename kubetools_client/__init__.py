# flake8: noqa

from pkg_resources import get_distribution

from .client import KubeClient

__version__ = get_distribution('kubetools').version
