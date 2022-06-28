from os import listdir, path
from unittest import mock, TestCase

import yaml

from kubetools.config import load_kubetools_config
from kubetools.kubernetes.api import check_if_cronjob_compatible, get_object_name
from kubetools.kubernetes.config import generate_kubernetes_configs_for_project
from kubetools.settings import get_settings


def _assert_yaml_objects(objects, yaml_filename):
    with open(yaml_filename, 'r') as f:
        desired_objects = list(yaml.safe_load_all(f))

    objects.sort(key=get_object_name)
    desired_objects.sort(key=get_object_name)

    assert objects == desired_objects


def _test_configs(folder_name, **kwargs):
    app_dir = path.join('tests', 'configs', folder_name)

    kubetools_config = load_kubetools_config(app_dir, **kwargs)
    settings = get_settings()

    with mock.patch('kubetools.kubernetes.config.job.uuid4', lambda: 'UUID'):
        services, deployments, jobs, cronjobs = generate_kubernetes_configs_for_project(
            kubetools_config,
        )

    k8s_files = listdir(app_dir)
    env = kubetools_config.get('env', settings.DEFAULT_KUBE_ENV)

    if services or 'k8s_services.yml' in k8s_files:
        _assert_yaml_objects(services, path.join(app_dir, 'k8s_services.yml'))
    if deployments or 'k8s_deployments.yml' in k8s_files:
        _assert_yaml_objects(deployments, path.join(app_dir, 'k8s_deployments.yml'))
    if jobs or 'k8s_jobs.yml' in k8s_files:
        _assert_yaml_objects(jobs, path.join(app_dir, 'k8s_jobs.yml'))
    if check_if_cronjob_compatible(env) is True and (cronjobs or 'k8s_cronjobs.yml' in k8s_files):
        _assert_yaml_objects(cronjobs, path.join(app_dir, 'k8s_cronjobs.yml'))
    if check_if_cronjob_compatible(env) is False and \
            (cronjobs or 'k8s_cronjobs_beta.yml' in k8s_files):
        _assert_yaml_objects(cronjobs, path.join(app_dir, 'k8s_cronjobs_beta.yml'))


class TestKubernetesConfigGeneration(TestCase):
    def test_basic_app_configs(self):
        _test_configs('basic_app')

    def test_dependencies_configs(self):
        _test_configs('dependencies')

    def test_dev_overrides_configs(self):
        _test_configs('dev_overrides', dev=True)

    def test_k8s_container_passthrough_configs(self):
        _test_configs('k8s_container_passthrough')

    def test_multiple_deployments_configs(self):
        _test_configs('multiple_deployments')
