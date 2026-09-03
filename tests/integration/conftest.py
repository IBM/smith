# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Pytest fixtures for Smith stage-level integration tests.

These tests drive the *real* ``smith`` CLI in place (against the real repo root,
real Makefile, real OPA server) with controlled, frozen inputs:

1. A **session-scoped backup** fixture snapshots the live ``assets/policy.rego``
   and ``references/test_cases/`` before any integration test runs and restores
   them afterwards — even if a test crashes — so overwriting those working
   files during a run is safe.
2. Frozen inputs live under ``tests/integration/fixtures/``. Because they are
   frozen, each flag's outcome is a known fixed number the tests assert exactly.
3. A **staging** helper (the ``stage`` fixture) copies the fixture subset a flag
   needs into the real locations right before invoking the CLI.

Every external dependency (Docker/OPA, LLM, target agent, ARES/Promptfoo) sits
behind a gating fixture that ``pytest.skip``s when absent, so the suite is safe
to run with nothing configured.

Shared non-fixture constants/helpers live in ``helpers.py``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from helpers import (
    CASE_FILE,
    DECOMP_FILE,
    EXAMPLE,
    FIXTURE_POLICY,
    FIXTURE_TEST_CASES,
    FLATTEN_FILE,
    GREY_GUIDANCE_FILE,
    REAL_POLICY,
    REAL_TEST_CASES,
    VARS_FILE,
    which,
)

# ---------------------------------------------------------------------------
# Snapshot helpers for the session backup/restore.
# ---------------------------------------------------------------------------


def _snapshot(src: Path, dst: Path) -> None:
    """Copy a file/dir to dst; record absence with a marker so restore can undo."""
    if src.is_dir():
        shutil.copytree(src, dst)
    elif src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.with_suffix(dst.suffix + ".absent").write_text("")


def _restore(backup: Path, target: Path) -> None:
    """Restore target from a snapshot produced by ``_snapshot``."""
    absent_marker = backup.with_suffix(backup.suffix + ".absent")
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
    elif target.exists():
        target.unlink()
    if absent_marker.exists():
        return  # original did not exist; leave target removed
    if backup.is_dir():
        shutil.copytree(backup, target)
    elif backup.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, target)


@pytest.fixture(scope="session", autouse=True)
def _backup_working_tree(tmp_path_factory):
    """Snapshot and later restore the live policy + test_cases (whole run)."""
    backup_dir = tmp_path_factory.mktemp("smith_working_backup")
    policy_bak = backup_dir / "policy.rego"
    cases_bak = backup_dir / "test_cases"

    _snapshot(REAL_POLICY, policy_bak)
    _snapshot(REAL_TEST_CASES, cases_bak)
    try:
        yield
    finally:
        _restore(policy_bak, REAL_POLICY)
        _restore(cases_bak, REAL_TEST_CASES)


# ---------------------------------------------------------------------------
# Staging: install frozen fixtures into the real locations for one test.
# ---------------------------------------------------------------------------


class Stager:
    """Installs frozen fixture inputs into the real repo locations."""

    def stage_policy(self, src: Path = FIXTURE_POLICY) -> Path:
        REAL_POLICY.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, REAL_POLICY)
        return REAL_POLICY

    def stage_test_cases(self, src: Path = FIXTURE_TEST_CASES) -> dict:
        """Replace references/test_cases/ with the frozen fixture set."""
        if REAL_TEST_CASES.exists():
            shutil.rmtree(REAL_TEST_CASES)
        shutil.copytree(src, REAL_TEST_CASES)
        return {
            label: len(list((REAL_TEST_CASES / label).glob("*.json")))
            for label in ("allow", "disallow")
            if (REAL_TEST_CASES / label).is_dir()
        }


@pytest.fixture
def stage() -> Stager:
    """Fresh stager per test; the session backup guarantees restore."""
    return Stager()


_GEN_ARTIFACTS = (
    DECOMP_FILE,
    FLATTEN_FILE,
    VARS_FILE,
    GREY_GUIDANCE_FILE,
    CASE_FILE,
)


@pytest.fixture
def isolate_generation_artifacts(tmp_path_factory):
    """Back up/restore the test_generation intermediate files around one test.

    Combined with the session-level test_cases backup, this leaves references/
    exactly as the test found it, so running test_generation in the full suite
    cannot leave stray artifacts that perturb other tests (or vice versa).
    """
    backup = tmp_path_factory.mktemp("gen_artifacts_backup")
    saved = {}
    for i, f in enumerate(_GEN_ARTIFACTS):
        if f.exists():
            dst = backup / f"{i}_{f.name}"
            shutil.copy2(f, dst)
            saved[f] = dst
    try:
        yield
    finally:
        for f in _GEN_ARTIFACTS:
            if f.exists():
                f.unlink()
            if f in saved:
                shutil.copy2(saved[f], f)


@pytest.fixture
def backup_file(tmp_path_factory):
    """Factory fixture: register a path to back up now and restore on teardown."""
    backup_dir = tmp_path_factory.mktemp("file_backup")
    registered = []  # (target, saved_copy_or_None_if_absent)

    def _register(path):
        path = Path(path)
        if path.exists():
            dst = backup_dir / (str(len(registered)) + "_" + path.name)
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


# ---------------------------------------------------------------------------
# Gating fixtures — each skips its test when the dependency is missing.
# ---------------------------------------------------------------------------


@pytest.fixture
def requires_llm():
    missing = [
        v
        for v in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_SONNET")
        if not os.getenv(v)
    ]
    if missing:
        pytest.skip(f"LLM not configured (missing {', '.join(missing)})")


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
def requires_ares():
    ares_home = os.getenv("ARES_HOME")
    if not ares_home or not Path(ares_home).exists():
        pytest.skip("ARES not installed (ARES_HOME unset or missing)")


@pytest.fixture
def requires_promptfoo():
    if not which("promptfoo"):
        pytest.skip("promptfoo CLI not found")


# ---------------------------------------------------------------------------
# The example target agent (FastAPI + stdio MCP).
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
def agent_server():
    """Boot the call-for-papers example agent (uvicorn + stdio MCP); yield its URL."""
    example = EXAMPLE
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
            pytest.skip(f"example agent did not become healthy:\n{out[-800:]}")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
