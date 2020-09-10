from os import path
from unittest import mock, TestCase

import yaml

from kubetools.config import load_kubetools_config
from kubetools.kubernetes.config import generate_kubernetes_configs_for_project


def _assert_yaml_objects(objects, yaml_filename):
    with open(yaml_filename, 'r') as f:
        desired_objects = list(yaml.safe_load_all(f))

    assert objects == desired_objects


class TestKubernetesConfigGeneration(TestCase):
    def test_basic_app_configs(self):
        app_dir = path.join('tests', 'configs', 'basic_app')

        kubetools_config = load_kubetools_config(app_dir)

        with mock.patch('kubetools.kubernetes.config.job.uuid4', lambda: 'UUID'):
            services, deployments, jobs = generate_kubernetes_configs_for_project(
                kubetools_config,
            )

        _assert_yaml_objects(services, path.join(app_dir, 'k8s_services.yml'))
        _assert_yaml_objects(deployments, path.join(app_dir, 'k8s_deployments.yml'))
        _assert_yaml_objects(jobs, path.join(app_dir, 'k8s_jobs.yml'))
