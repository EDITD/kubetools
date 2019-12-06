#!/usr/bin/env python

from kubetools_client.cli import cli_bootstrap
from kubetools_client.main import run_cli
# Import click command groups
from kubetools_client.cli import (  # noqa: F401, I100
    configs,
    deploy,
    server,
)


run_cli(cli_bootstrap)
