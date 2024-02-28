from string import ascii_lowercase
from unittest import TestCase

from kubetools.dev.backends.docker_compose.config import dockerise_label
from kubetools.dev.backends.docker_compose.docker_util import _get_container_name_from_full_name


def generate_long_names(number_of_separators, separator):
    return separator.join([
        ch for ch in ascii_lowercase[:number_of_separators+1]])


class TestDockerComposeNameConversion(TestCase):
    # we need to check this works for dashes and underscores
    def test_dockerise_label_dashes(self):
        for i in range(5):
            long_name = generate_long_names(i, '-')
            dockerised_name = dockerise_label(long_name)
            self.assertEqual(dockerised_name, ascii_lowercase[:i+1])

    def test_dockerise_label_underscores(self):
        for i in range(5):
            long_name = generate_long_names(i, '_')
            dockerised_name = dockerise_label(long_name)
            self.assertEqual(dockerised_name, ascii_lowercase[:i+1])

    def test_container_name_from_full_name_dashes(self):
        for i in range(5):
            container_name = generate_long_names(i, '-')
            full_name = '-'.join([ascii_lowercase[:i+1], container_name, '1'])
            self.assertEqual(_get_container_name_from_full_name(full_name), container_name)

    def test_container_name_from_full_name_underscores(self):
        for i in range(5):
            container_name = generate_long_names(i, '-')
            full_name = '_'.join([ascii_lowercase[:i+1], container_name, '1'])
            self.assertEqual(_get_container_name_from_full_name(full_name), container_name)
