# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag duplication_suggestion``.

The flag looks for redundancy in the policy two independent ways and concatenates
both reports::

    init_graph                       opa parse -> AST -> a rule-call graph
    update_policy_analysis_feedback  LLM: duplicate / cyclic / dead rules
    write_graph_suggestion           GRAPH: rules unreachable from `allow`

Driven through the **real CLI** with real ``opa parse`` and a real model. This file
imports nothing from ``smith``, so every assertion reads the run's stdout or an
artifact it left behind.

STEPS COVERED (all from the single run)
--------------------------------------
STEP 1  ``init_graph``        — a real AST becomes a graph on disk
STEP 2  the LLM half          — its section is present and reached a verdict
STEP 3  the graph half        — the unreachability report, from the real graph
STEP 4  both halves concatenated onto stdout, in order

COST: THE FLAG IS RUN ONCE
--------------------------
It shells out to ``opa parse`` and makes LLM calls over the whole policy. So it runs
**exactly once** in a module-scoped fixture and every assertion inspects that run.

ASSERTING CORRECTNESS
---------------------
The two halves warrant different treatment:

* The **graph half is deterministic** — set arithmetic over a parsed AST — so its
  output is asserted structurally and, crucially, checked for the property that
  matters: no rule reachable from ``allow`` may be reported as dead. Suggesting a
  live rule be deleted would break the policy.
* The **LLM half is a judgement**, so only its presence and non-degradation are
  asserted. Which rules a model calls duplicative is exactly what it is there to
  decide.

The staged policy, the graph artifacts and both suggestion files are backed up and
restored.

Requires Docker (for the containerised ``opa parse``) and a real LLM.
"""

from __future__ import annotations

import re

import pytest

pytestmark = pytest.mark.integration


#: The two section headers ``get_duplication_feedback`` concatenates, in order.
LLM_HEADER = "Below is LLM generated redundancy suggestions:"
GRAPH_HEADER = "Below is graph generated redundancy suggestions"


@pytest.fixture(scope="module")
def completed_run():
    """Run ``duplication_suggestion`` ONCE over the frozen fixture policy."""
    import shutil
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    from helpers import FIXTURE_POLICY, SmithEnv, which

    env = SmithEnv()
    missing = env.missing("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_SONNET")
    if missing:
        pytest.skip(f"Smith LLM not configured (missing {', '.join(missing)})")
    # `create_ast` runs `opa parse` inside a container rather than using a local
    # binary, so Docker is the real prerequisite here.
    if not which("docker"):
        pytest.skip("docker CLI not found (init_graph runs `opa parse` in a container)")

    policy = env.policy
    outputs = Path(env.base) / env.env["DATA_DIR"] / "outputs"
    graph = outputs / env.env["GRAPH_PATH"]
    graph_suggestion = outputs / env.env["GRAPH_SUGGESTION_PATH"]
    ast_path = outputs / env.env["OPA_AST_PATH"]

    # The LLM half writes one .json + .md pair per analysis into the same outputs
    # directory, so they are protected too — otherwise a run leaves six untracked
    # files behind in the developer's tree.
    llm_reports = [
        outputs / f"linting_feedback_{name}.{suffix}"
        for name in ("de-duplication", "cycle-detection", "deadrules")
        for suffix in ("json", "md")
    ]
    protected = [policy, graph, graph_suggestion, ast_path, *llm_reports]
    backup_dir = Path(tempfile.mkdtemp(prefix="smith_dup_backup_"))
    saved = {}
    for i, path in enumerate(protected):
        if path.exists():
            saved[path] = backup_dir / f"{i}_{path.name}"
            shutil.copy2(path, saved[path])

    try:
        policy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIXTURE_POLICY, policy)
        for path in (graph, graph_suggestion, ast_path):
            if path.exists():
                path.unlink()

        result = subprocess.run(
            [sys.executable, "-m", "smith.cli", "--flag", "duplication_suggestion"],
            cwd=str(env.base),
            env=env.override(),
            capture_output=True,
            text=True,
            timeout=1800,
        )
        yield {
            "result": result,
            "policy": policy,
            "graph": graph,
            "graph_suggestion": graph_suggestion,
            "ast": ast_path,
        }
    finally:
        for path in protected:
            if path.exists():
                path.unlink()
            if path in saved:
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(saved[path], path)
        shutil.rmtree(backup_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def run_ok(completed_run):
    """The run must have succeeded before any artifact assertion is meaningful."""
    result = completed_run["result"]
    assert result.returncode == 0, (
        f"duplication_suggestion failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-3000:]}\n"
        f"--- stderr ---\n{result.stderr[-1500:]}"
    )
    return completed_run


@pytest.fixture(scope="module")
def stdout(run_ok):
    """The concatenated report — what the flag prints and the loop consumes."""
    return run_ok["result"].stdout


# ===========================================================================
# STEP 1 — the real AST became a graph
# ===========================================================================


def test_the_policy_was_parsed_into_a_graph(run_ok):
    # `init_graph` shells out to `opa parse` and writes the graph as DOT. Without it
    # the graph half has nothing to analyse.
    graph = run_ok["graph"]
    assert (
        graph.exists()
    ), f"no graph written to {graph}\n{run_ok['result'].stdout[-2000:]}"
    assert graph.read_text().strip(), "the graph file is empty"


def test_the_graph_uses_the_indexed_node_naming_the_analysis_expects(run_ok):
    """CORRECTNESS: the node-name shape the unit lane hand-builds is confirmed here."""
    dot = run_ok["graph"].read_text()
    assert re.search(
        r'"\d+& \w+"', dot
    ), f"no indexed node names found in the graph: {dot[:400]!r}"
    assert "& allow" in dot, "the graph has no allow rule, so it has no analysis root"


# ===========================================================================
# STEP 2 — the LLM half
# ===========================================================================


def test_the_llm_section_is_present_and_reached_a_verdict(stdout):
    # Which rules a model calls duplicative is its own judgement, so only presence
    # and non-degradation are asserted. An empty section means the paid call produced
    # nothing usable.
    assert LLM_HEADER in stdout
    llm_section = stdout.split(LLM_HEADER, 1)[1].split(GRAPH_HEADER, 1)[0]
    assert llm_section.strip(), "the LLM half produced no content at all"


# ===========================================================================
# STEP 3 — the graph half, and the property that matters
# ===========================================================================


def test_the_graph_suggestion_is_written_and_explains_itself(run_ok):
    path = run_ok["graph_suggestion"]
    assert path.exists(), f"no graph suggestion at {path}"
    text = path.read_text()
    assert "unreachable" in text, (
        "the report must explain what a subgraph represents — it is read by both a "
        "human and a model"
    )


def test_no_rule_reachable_from_allow_is_reported_as_dead(run_ok):
    text = run_ok["graph_suggestion"].read_text()
    reported = set()
    for match in re.finditer(r"node:\n\[(.*?)\]", text, re.DOTALL):
        reported |= {name.strip().strip("'\"") for name in match.group(1).split(",")}
    reported.discard("")

    for live in ("allow", "valid_envelope", "any_deny"):
        assert live not in reported, (
            f"{live!r} is reachable from allow but was reported as redundant: "
            f"{sorted(reported)}"
        )


# ===========================================================================
# STEP 4 — both halves reach the user, in order
# ===========================================================================


def test_both_sections_are_printed_in_order(stdout):
    # The flag concatenates LLM then graph. The order is what lets a reader tell
    # which analysis produced which finding — they warrant different trust.
    assert LLM_HEADER in stdout and GRAPH_HEADER in stdout
    assert stdout.index(LLM_HEADER) < stdout.index(GRAPH_HEADER)


def test_the_graph_section_on_stdout_matches_the_written_file(stdout, run_ok):
    # The return value and the file must not diverge: a user reading stdout and a
    # tool reading the file have to see the same findings.
    written = run_ok["graph_suggestion"].read_text().strip()
    assert written in stdout


def test_the_policy_is_not_modified(run_ok):
    from helpers import FIXTURE_POLICY

    assert run_ok["policy"].read_text() == FIXTURE_POLICY.read_text()
