# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Pytest fixtures for the Smith test suite.

This directory holds **all three** test categories. The marker, not the directory
name, decides what runs — see ``README.md``:

* ``unit``        — env-free: no ``.env``, no credentials, no external service.
                    Calls individual functions directly. This is the subset
                    ``make ci`` runs in GitHub Actions.
* ``integration`` — exercises each ``smith`` CLI flag's real execution against
                    the real checkout, using the developer's ``.env`` — including
                    the tests that call a real LLM, which gate on
                    ``requires_llm``.

Two fixtures supply the environment, one per lane (both classes live in
``helpers.py`` and share the same accessors, so a test names ``env.policy``
whichever lane it is in):

* ``smith_env`` → ``SmithEnv``: the real ``.env`` configuration, for
  integration tests. Those that overwrite a real artifact protect it with
  ``backup_file``.
* ``unit_env`` → ``UnitEnv``: a preset environment whose *inputs* resolve to the
  frozen ``fixtures/`` tree and whose *outputs* resolve under ``tmp_path``.

Integration tests keep driving the real CLI in place:

1. Frozen inputs live under ``tests/integration/fixtures/``. Because they are
   frozen, each flag's outcome is a known fixed number the tests assert exactly.
2. A **staging** helper (the ``stage`` fixture) copies the fixture subset a flag
   needs into the real locations right before invoking the CLI.
3. ``backup_file`` protects each real file a test overwrites, restoring it on
   teardown — explicitly requested, so unit tests never inherit it.

Shared non-fixture constants/helpers live in ``helpers.py``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from helpers import (
    FIXTURE_POLICY,
    FIXTURE_TEST_CASES,
    SmithEnv,
    UnitEnv,
    which,
)

# The three mutually exclusive primary categories.
PRIMARY_MARKERS = ("unit", "integration")

#: Cached real environment; built on first use, never at import (see docstring).
_real_env: SmithEnv | None = None


def real_env() -> SmithEnv:
    """The real ``.env`` environment, resolved lazily and cached.

    Only the integration machinery calls this, so a unit-only run never
    assembles a configured path.
    """
    global _real_env
    if _real_env is None:
        _real_env = SmithEnv()
    return _real_env


# ---------------------------------------------------------------------------
# Collection-time marker enforcement.
#
# ``--strict-markers`` only rejects *unknown* marker names; it neither requires a
# marker nor forbids two conflicting ones. Exactly one primary category per test,
# including markers inherited from a class or module.
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config, items):
    problems = []
    for item in items:
        found = {m for m in PRIMARY_MARKERS if item.get_closest_marker(m)}
        if len(found) != 1:
            problems.append(
                f"  {item.nodeid}: "
                + (
                    "no primary marker"
                    if not found
                    else f"conflicting markers {sorted(found)}"
                )
            )
    if problems:
        raise pytest.UsageError(
            "Every test needs exactly one primary marker "
            f"({', '.join(PRIMARY_MARKERS)}):\n" + "\n".join(problems)
        )


@pytest.fixture
def unit_env(tmp_path) -> UnitEnv:
    return UnitEnv(tmp_path)


@pytest.fixture
def smith_env() -> SmithEnv:
    return real_env()


# ---------------------------------------------------------------------------
# The CLI runner.
#
# Resolves the CLI from *this* project environment (``sys.executable -m
# smith.cli``), so the subject under test is the checkout — never an unrelated
# ``smith`` binary that happens to be first on PATH.
# ---------------------------------------------------------------------------


@pytest.fixture
def smith_cli(smith_env):
    """Run a ``smith`` flag against the real environment."""

    class Runner:
        executable = [sys.executable, "-m", "smith.cli"]

        def __call__(self, flag, *extra_args, timeout=900, **overrides):
            return self.argv("--flag", flag, *extra_args, timeout=timeout, **overrides)

        def argv(self, *args, timeout=900, env=None, **overrides):
            child_env = smith_env.override(**overrides) if env is None else dict(env)
            return subprocess.run(
                [*self.executable, *args],
                cwd=str(smith_env.base),
                env=child_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

    return Runner()


# ---------------------------------------------------------------------------
# Backup/restore of real working-tree files.
#
# Explicitly requested only — never autouse, so a unit test cannot inherit it.
# ``backup_file`` is the single implementation; the fixtures below build on it.
# ---------------------------------------------------------------------------


@pytest.fixture
def backup_file(tmp_path_factory):
    """Factory: register a real path to back up now and restore on teardown.

    Handles files and directories, and records absence with a marker so a path
    that did not exist beforehand is removed again rather than left behind.
    """
    backup_dir = tmp_path_factory.mktemp("file_backup")
    registered = []  # (target, saved_copy_or_None_if_absent)

    def _register(path):
        path = Path(path)
        if path.exists():
            dst = backup_dir / f"{len(registered)}_{path.name}"
            if path.is_dir():
                shutil.copytree(path, dst)
            else:
                shutil.copy2(path, dst)
            registered.append((path, dst))
        else:
            registered.append((path, None))
        return path

    yield _register

    for target, saved in registered:
        # Clear whatever is currently at the target (file or dir).
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()
        if saved is None:
            continue  # original did not exist -> leave target removed
        if saved.is_dir():
            shutil.copytree(saved, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(saved, target)


@pytest.fixture
def backup_working_tree(backup_file):
    """Protect the live policy + test_cases for one test.

    **Explicitly requested, never autouse.** Unit tests never touch these files,
    so they must not inherit (or pay for) backup/restore.
    """
    env = real_env()
    backup_file(env.policy)
    backup_file(env.test_cases)
    return env


@pytest.fixture
def isolate_generation_artifacts(backup_file):
    """Protect the ``test_generation`` intermediate files around one test.

    So running generation in the full suite cannot leave stray artifacts that
    perturb other tests (or vice versa).
    """
    for path in real_env().generation_artifacts.values():
        backup_file(path)


# ---------------------------------------------------------------------------
# Staging: install frozen fixtures into the real locations for one test.
# ---------------------------------------------------------------------------


class Stager:
    """Installs frozen fixture inputs into the real repo locations."""

    def __init__(self, env: SmithEnv):
        self.env = env

    def stage_policy(self, src: Path = FIXTURE_POLICY) -> Path:
        self.env.policy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, self.env.policy)
        return self.env.policy

    def stage_test_cases(self, src: Path = FIXTURE_TEST_CASES) -> dict:
        """Replace references/test_cases/ with the frozen fixture set."""
        cases = self.env.test_cases
        if cases.exists():
            shutil.rmtree(cases)
        shutil.copytree(src, cases)
        return {
            label: len(list((cases / label).glob("*.json")))
            for label in ("allow", "disallow")
            if (cases / label).is_dir()
        }


@pytest.fixture
def stage(backup_working_tree) -> Stager:
    """Fresh stager per test.

    Depends on ``backup_working_tree`` because staging overwrites the live policy
    and case set: requesting the stager is what opts a test into restoring them.
    """
    return Stager(backup_working_tree)


# ---------------------------------------------------------------------------
# Gating fixtures — each skips its own test when its dependency is missing.
# Requested explicitly by integration tests; never reachable from a unit test.
# ---------------------------------------------------------------------------


@pytest.fixture
def requires_llm(smith_env):
    """Smith's own LLM settings — distinct from the example agent's INFERENCE_*."""
    missing = smith_env.missing("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_SONNET")
    if missing:
        pytest.skip(f"Smith LLM not configured (missing {', '.join(missing)})")
    return smith_env


@pytest.fixture
def requires_agent_inference(smith_env):
    """The example agent's own model settings — a different consumer entirely."""
    missing = smith_env.missing(
        "INFERENCE_MODEL", "INFERENCE_BASE_URL", "INFERENCE_API_KEY"
    )
    if missing:
        pytest.skip(f"agent inference not configured (missing {', '.join(missing)})")
    return smith_env


@pytest.fixture
def requires_docker():
    if not which("docker"):
        pytest.skip("docker CLI not found")
    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pytest.skip("docker daemon not responding")


@pytest.fixture
def requires_make():
    if not which("make"):
        pytest.skip("make not found")


@pytest.fixture
def requires_opa_binary():
    """Skip unless the ``opa`` CLI is on PATH (used by policy_validation)."""
    if not which("opa"):
        pytest.skip("opa binary not found on PATH")


@pytest.fixture
def requires_regal():
    """Skip unless the ``regal`` CLI is on PATH (used by regal_suggestion)."""
    if not which("regal"):
        pytest.skip("regal binary not found on PATH")


@pytest.fixture
def requires_ares(smith_env):
    ares_home = smith_env.env.get("ARES_HOME")
    if not ares_home or not Path(ares_home).exists():
        pytest.skip("ARES not installed (ARES_HOME unset or missing)")


@pytest.fixture
def requires_promptfoo():
    if not which("promptfoo"):
        pytest.skip("promptfoo CLI not found")


# ---------------------------------------------------------------------------
# The example target agent (FastAPI + stdio MCP) — opt-in, integration only.
# ---------------------------------------------------------------------------


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_health(url: str, timeout: float) -> bool:
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:  # noqa: S310
                if resp.status == 200:
                    return True
        except urllib.error.HTTPError:
            return True  # up, just not 200
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.5)
    return False


@pytest.fixture
def agent_server(smith_env):
    """Boot the call-for-papers example agent (uvicorn + stdio MCP); yield its URL.

    Skips only for a genuinely absent prerequisite. Once the prerequisites hold, a
    startup failure **fails** the test rather than masquerading as a missing
    dependency — a broken example agent is a real problem, not a reason to pass.
    """
    example = smith_env.example
    if not (example / "agent.py").exists():
        pytest.skip("call-for-papers example not found")
    if not which("uvicorn"):
        pytest.skip("uvicorn not installed")

    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        ["uvicorn", "agent:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(example),
        env=dict(os.environ),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        if not _wait_for_health(f"{url}/health", timeout=45):
            proc.terminate()
            out = ""
            try:
                out = proc.communicate(timeout=5)[0] or ""
            except subprocess.TimeoutExpired:
                proc.kill()
            pytest.fail(f"example agent did not become healthy:\n{out[-1500:]}")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
