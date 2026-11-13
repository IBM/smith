# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration test: the OWASP catalog ships in the built wheel.

Phases C and D read ``smith/data/owasp_10_ai_catalog.json`` through
``smith.tools.security_catalog.CATALOG_PATH``. An editable install finds it in
the checkout, so only a real wheel shows whether ``package-data`` ships it.

The wheel is built from a copy of the build inputs under ``tmp_path``, installed
into a fresh venv without dependencies, and the catalog is loaded from outside
the checkout. Nothing in the working tree is written.

Requires: ``setuptools`` and ``pip`` in the current interpreter; no network.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
BUILD_INPUTS = ("pyproject.toml", "README.md", "LICENSE", "src")


@pytest.fixture(scope="module")
def installed_wheel(tmp_path_factory):
    """Build and install the wheel ONCE; yield the venv's interpreter."""
    if importlib.util.find_spec("setuptools") is None:
        pytest.skip("setuptools is not installed; cannot build the wheel offline")
    base = tmp_path_factory.mktemp("wheel")
    source = base / "source"
    source.mkdir()
    for name in BUILD_INPUTS:
        origin = REPO / name
        if origin.is_dir():
            # An editable install leaves ``*.egg-info/SOURCES.txt`` listing every
            # file; setuptools would ship from it and hide a package-data gap.
            shutil.copytree(
                origin,
                source / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"),
            )
        elif origin.is_file():
            shutil.copy2(origin, source / name)
    dist = base / "dist"
    build = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation"]
        + ["-q", "-w", str(dist), str(source)],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr[-2500:]
    (wheel,) = dist.glob("smith-*.whl")
    venv = base / "venv"
    subprocess.run(
        [getattr(sys, "_base_executable", sys.executable), "-m", "venv", str(venv)],
        check=True,
    )
    python = venv / ("Scripts" if sys.platform == "win32" else "bin") / "python"
    install = subprocess.run(
        [str(python), "-m", "pip", "install", "-q", "--no-deps", str(wheel)],
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, install.stderr[-2500:]
    yield {"python": python, "cwd": base}


def test_installed_wheel_loads_the_catalog(installed_wheel):
    probe = (
        "from smith.tools.security_catalog import CATALOG_PATH, load_catalog\n"
        "catalog = load_catalog(CATALOG_PATH)\n"
        "print(CATALOG_PATH)\n"
        "print(sum(catalog.scenario_counts.values()))\n"
    )
    result = subprocess.run(
        [str(installed_wheel["python"]), "-c", probe],
        capture_output=True,
        text=True,
        cwd=installed_wheel["cwd"],
    )

    assert result.returncode == 0, result.stderr[-2500:]
    path, scenarios = result.stdout.split()
    assert "site-packages" in path, "the catalog must come from the installed wheel"
    assert scenarios == "61"
