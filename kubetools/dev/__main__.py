#!/usr/bin/env python

from kubetools.dev import dev
from kubetools.main import run_cli

# Import click command groups
from kubetools.dev import (  # noqa: F401, I100, I202
    container,
    environment,
    logs,
    scripts,
)


run_cli(dev)
