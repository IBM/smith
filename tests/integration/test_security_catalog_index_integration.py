# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag security_catalog_index``.

Builds the index over the shipped catalog with the real MiniLM encoder, then
queries it::

    --build              real all-MiniLM-L6-v2 -> scenarios.npz, mitigations.npz
    (no option)          manifest + freshness
    --query --phase C|D  ranked and cross-category hits

Driven through the **real CLI**; every assertion reads its output or the files
it wrote. The index goes to a temporary directory via
``SECURITY_CATALOG_INDEX_DIR``, so nothing in the working tree changes.

COST
----
No LLM, no agent, no OPA, no Docker. The only model is the local sentence
embedder, ~90MB on first use and cached thereafter, so the build runs **once**
in a module-scoped fixture.

ASSERTING CORRECTNESS
---------------------
Ranking is a model-driven judgement, so exact orders are not asserted. What is:

* **A query naming one category's subject ranks that category's scenario
  first.** The query quotes the catalog's own wording for an ASI06 memory
  poisoning scenario, so any sentence embedder puts it on top.
* Item counts (61 / 300) and the manifest hash are bookkeeping, so exact.
* A Phase D query restricted to two categories lists only those categories under
  ``Ranked`` and only other categories under ``Cross-category candidates``.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "src" / "smith" / "data" / "owasp_10_ai_catalog.json"


def run(index_dir: Path, *args: str) -> subprocess.CompletedProcess:
    env = {
        **__import__("os").environ,
        "BASE_URL": str(REPO) + "/",
        "SECURITY_CATALOG_INDEX_DIR": str(index_dir),
    }
    return subprocess.run(
        [sys.executable, "-m", "smith.cli", "--flag", "security_catalog_index", *args],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )


@pytest.fixture(scope="module")
def built_index():
    """Build the index ONCE for this module; yield its directory."""
    pytest.importorskip("sentence_transformers")
    index_dir = Path(tempfile.mkdtemp(prefix="smith_catalog_index_")) / "index"
    result = run(index_dir, "--build")
    if result.returncode != 0 and "huggingface" in (result.stderr or "").lower():
        pytest.skip("MiniLM weights are unavailable (offline, not cached)")
    assert result.returncode == 0, result.stderr[-2500:]
    return {"dir": index_dir, "build": result}


def test_build_indexes_every_catalog_item(built_index):
    assert "61 scenarios, 300 mitigation items" in built_index["build"].stdout
    manifest = json.loads((built_index["dir"] / "manifest.json").read_text())
    assert manifest["catalog_sha256"] == hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    assert manifest["dimensions"] == 384


def test_status_reports_fresh(built_index):
    result = run(built_index["dir"])

    assert result.returncode == 0
    assert "OWASP catalog index: FRESH" in result.stdout


def test_query_ranks_its_own_category_first(built_index):
    catalog = json.loads(CATALOG.read_text())
    asi06 = next(entry for entry in catalog["threats"] if entry["id"] == "ASI06")
    query = asi06["attack_scenarios"][0]

    result = run(built_index["dir"], "--query", query, "--phase", "C")

    assert result.returncode == 0, result.stderr[-2500:]
    first = re.search(r"^\s+[\d.]+\s+(ASI\d\d)#\d+", result.stdout, re.MULTILINE)
    assert first and first.group(1) == "ASI06", result.stdout


def test_phase_d_query_separates_ranked_and_cross_category_hits(built_index):
    result = run(
        built_index["dir"],
        "--query",
        "attacker manipulates the agent into calling a privileged tool",
        "--phase",
        "D",
        "--asi",
        "ASI01,ASI02",
    )

    assert result.returncode == 0, result.stderr[-2500:]
    ranked, _, added = result.stdout.partition("Cross-category candidates")
    ranked_asi = set(re.findall(r"^\s+[\d.]+\s+(ASI\d\d)/", ranked, re.MULTILINE))
    added_asi = set(re.findall(r"^\s+[\d.]+\s+(ASI\d\d)/", added, re.MULTILINE))
    assert ranked_asi and ranked_asi <= {"ASI01", "ASI02"}
    assert added_asi and not added_asi & {"ASI01", "ASI02"}
