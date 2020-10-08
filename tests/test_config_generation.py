from os import path
from unittest import mock, TestCase

import yaml

from kubetools.config import load_kubetools_config
from kubetools.kubernetes.api import get_object_name
from kubetools.kubernetes.config import generate_kubernetes_configs_for_project


def _assert_yaml_objects(objects, yaml_filename):
    with open(yaml_filename, 'r') as f:
        desired_objects = list(yaml.safe_load_all(f))

    objects.sort(key=get_object_name)
    desired_objects.sort(key=get_object_name)

    assert objects == desired_objects


def _test_configs(folder_name, **kwargs):
    app_dir = path.join('tests', 'configs', folder_name)

    kubetools_config = load_kubetools_config(app_dir, **kwargs)

    with mock.patch('kubetools.kubernetes.config.job.uuid4', lambda: 'UUID'):
        services, deployments, jobs = generate_kubernetes_configs_for_project(
            kubetools_config,
        )

    if services:
        _assert_yaml_objects(services, path.join(app_dir, 'k8s_services.yml'))
    if deployments:
        _assert_yaml_objects(deployments, path.join(app_dir, 'k8s_deployments.yml'))
    if jobs:
        _assert_yaml_objects(jobs, path.join(app_dir, 'k8s_jobs.yml'))


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
