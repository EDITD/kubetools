from unittest import TestCase

from kubetools.dev.backends.docker_compose import build_run_compose_command


class TestBuildComposeCommand(TestCase):
    def setUp(self):
        self.container = 'container'

    def test_simple_composite_command(self):
        command = ('python', 'scripts/blah.py', '--argument')
        result = build_run_compose_command(self.container, command, envvars=None)
        expected_result = ['run', '--entrypoint', 'python scripts/blah.py --argument', 'container']
        self.assertEqual(expected_result, result)

    def test_simple_single_command(self):
        command = ('python scripts/blah.py --argument',)
        result = build_run_compose_command(self.container, command, envvars=None)
        expected_result = ['run', '--entrypoint', 'python scripts/blah.py --argument', 'container']
        self.assertEqual(expected_result, result)

    def test_composite_command_is_shell_escaped(self):
        command = ('python', 'scripts/blah.py', '--argument', 'key: value')
        result = build_run_compose_command(self.container, command, envvars=None)
        expected_result = [
            'run',
            '--entrypoint',
            "python scripts/blah.py --argument 'key: value'",
            'container',
        ]
        self.assertEqual(expected_result, result)

    def test_environment_variables_are_added(self):
        command = ('python', 'scripts/blah.py', '--argument')
        envvars = ('var1=val1', 'var2=val2')
        result = build_run_compose_command(self.container, command, envvars)
        expected_result = [
            'run',
            '-evar1=val1',
            '-evar2=val2',
            '--entrypoint',
            'python scripts/blah.py --argument',
            'container',
        ]
        self.assertEqual(expected_result, result)
