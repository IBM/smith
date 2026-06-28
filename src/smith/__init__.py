# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
"""Smith — automated policy lifecycle management for AI agents (OPA/Rego)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("smith")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0"
