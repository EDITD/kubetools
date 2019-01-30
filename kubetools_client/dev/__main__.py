#!/usr/bin/env python

from kubetools_client.dev import dev
from kubetools_client.main import run_cli

# Import click command groups
from kubetools_client.dev import container, environment, logs, scripts  # noqa: F401, I100


run_cli(dev)
