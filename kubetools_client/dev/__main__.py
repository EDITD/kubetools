#!/usr/bin/env python

from kubetools_client.dev import dev
from kubetools_client.main import run_cli

# Import click command groups
from kubetools_client.dev import (  # noqa: F401, I100, I202
    container,
    environment,
    logs,
    scripts,
)


run_cli(dev)
