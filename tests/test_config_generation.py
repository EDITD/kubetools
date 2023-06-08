from os import listdir, path
from unittest import mock, TestCase

import yaml

from kubetools.config import load_kubetools_config
from kubetools.deploy.image import get_container_contexts_from_config, get_docker_tag_for_commit
from kubetools.kubernetes.api import get_object_name
from kubetools.kubernetes.config import generate_kubernetes_configs_for_project


class TestKubernetesConfigGeneration(TestCase):
    def test_basic_app_configs(self):
        _test_configs('basic_app')

    def test_dependencies_configs(self):
        _test_configs('dependencies')

    def test_dev_overrides_configs(self):
        _test_configs('dev_overrides', dev=True)

    def test_k8s_container_passthrough_configs(self):
        _test_configs('k8s_container_passthrough')

    def test_k8s_cronjobs_beta_api_version_configs(self):
        _test_configs('k8s_cronjobs_beta_api_version')

    def test_multiple_deployments_configs(self):
        _test_configs('multiple_deployments')

    def test_docker_registry_configs(self):
        _test_configs('docker_registry', default_registry='default-registry')

    def test_k8s_with_mounted_secrets_configs(self):
        _test_configs('k8s_with_mounted_secrets')


def _test_configs(folder_name, default_registry=None, **kwargs):
    app_dir = path.join('tests', 'configs', folder_name)

    kubetools_config = load_kubetools_config(app_dir, **kwargs)

    # TODO: refactor deploy.image._ensure_docker_images to extract the logic to a function and
    #  de-duplicate it from here
    build_contexts = get_container_contexts_from_config(kubetools_config)
    context_name_to_registry = {
        context_name: build_context.get('registry', default_registry)
        for context_name, build_context in build_contexts.items()
    }
    context_images = {
        # Build the context name -> image dict
        context_name: get_docker_tag_for_commit(
            context_name_to_registry[context_name],
            kubetools_config['name'],
            context_name,
            'thisisacommithash',
        )
        for context_name in build_contexts.keys()
    }

    with mock.patch('kubetools.kubernetes.config.job.uuid4', lambda: 'UUID'):
        services, deployments, jobs, cronjobs = generate_kubernetes_configs_for_project(
            kubetools_config,
            default_registry=default_registry,
            context_name_to_image=context_images,
        )

    k8s_files = listdir(app_dir)

    if services or 'k8s_services.yml' in k8s_files:
        _assert_yaml_objects(services, path.join(app_dir, 'k8s_services.yml'))
    if deployments or 'k8s_deployments.yml' in k8s_files:
        _assert_yaml_objects(deployments, path.join(app_dir, 'k8s_deployments.yml'))
    if jobs or 'k8s_jobs.yml' in k8s_files:
        _assert_yaml_objects(jobs, path.join(app_dir, 'k8s_jobs.yml'))
    if cronjobs and 'k8s_cronjobs.yml' in k8s_files:
        _assert_yaml_objects(cronjobs, path.join(app_dir, 'k8s_cronjobs.yml'))
    if cronjobs and 'k8s_cronjobs_beta.yml' in k8s_files:
        _assert_yaml_objects(cronjobs, path.join(app_dir, 'k8s_cronjobs_beta.yml'))


def _assert_yaml_objects(objects, yaml_filename):
    with open(yaml_filename, 'r') as f:
        desired_objects = list(yaml.safe_load_all(f))

    objects.sort(key=get_object_name)
    desired_objects.sort(key=get_object_name)

    assert objects == desired_objects
