from os import path
from unittest import TestCase

from kubetools.config import load_kubetools_config
from kubetools.kubernetes.config import make_job_config


def load_job_spec():
    app_dir = path.join('tests', 'configs', 'basic_app')
    kubetools_config = load_kubetools_config(app_dir)
    return kubetools_config.get('upgrades')[0]


class TestMakeJobConfig(TestCase):
    def test_job_id_is_added_to_envvars(self):
        job_config = make_job_config(load_job_spec())
        container_env = job_config['spec']['template']['spec']['containers'][0]['env']
        self.assertIn('KUBE_JOB_ID', [env['name'] for env in container_env])

    def test_job_name_defaults_to_job_id(self):
        job_config = make_job_config(load_job_spec())
        job_name = job_config['metadata']['name']
        job_id = job_config['metadata']['labels']['job-id']
        self.assertEqual(job_name, job_id)

    def test_job_name_can_be_set_by_caller(self):
        job_config = make_job_config(load_job_spec(), job_name='myawesomejob')
        job_name = job_config['metadata']['name']
        self.assertEqual('myawesomejob', job_name)

    def test_container_name_defaults_to_upgrade(self):
        job_config = make_job_config(load_job_spec())
        container_name = job_config['spec']['template']['spec']['containers'][0]['name']
        self.assertEqual('upgrade', container_name)

    def test_container_name_can_be_set_by_caller(self):
        job_config = make_job_config(load_job_spec(), container_name='mycoolcontainer')
        container_name = job_config['spec']['template']['spec']['containers'][0]['name']
        self.assertEqual('mycoolcontainer', container_name)

    def test_resources_being_passed(self):
        expected_resources = {
            "requests": {
                "memory": "1Gi",
            },
        }
        job_config = make_job_config(load_job_spec())
        resource_config = job_config['spec']['template']['spec']['containers'][0]['resources']
        self.assertEqual(expected_resources, resource_config)

    def test_ttl_is_set_if_provided_in_config(self):
        job_spec = load_job_spec()
        ttl_option = {'ttl_seconds_after_finished': 100}
        job_spec.update(ttl_option)
        job_config = make_job_config(job_spec)
        self.assertIn('ttlSecondsAfterFinished', job_config['spec'])
        self.assertEqual(
            job_config['spec']['ttlSecondsAfterFinished'],
            ttl_option['ttl_seconds_after_finished'],
        )
