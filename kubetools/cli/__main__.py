#!/usr/bin/env python

from kubetools.cli import cli_bootstrap
from kubetools.main import run_cli
# Import click command groups
from kubetools.cli import deploy, generate_config, show  # noqa: F401, I100


run_cli(cli_bootstrap)
