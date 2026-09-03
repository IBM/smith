# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for the refinement-suggestion flags ``regal_suggestion`` and
``duplication_suggestion``.

We craft several policies (not read from a fixture) and check the suggestions
are *effective* — that they actually identify the planted defect and stay quiet
when there is none.

- ``regal_suggestion`` -> ``create_regal_suggestion(policy, out)`` runs
  ``regal lint``. LLM-free/deterministic: a policy with planted style issues
  (``= false`` instead of ``:=``, a braces rule with no ``if``) must flag the
  matching Regal rules; a clean policy must NOT flag them. Needs the ``regal``
  binary.

- ``duplication_suggestion`` has two halves. The GRAPH half
  (``init_graph`` + ``write_graph_suggestion``) is LLM-free and finds rules
  unreachable from ``allow`` (dead/redundant). We assert a policy with a planted
  dead rule names it as redundant, and a tight policy (every rule feeds
  ``allow``) does not. It parses the AST via the OPA Docker image, so it needs
  Docker. One end-to-end test also drives the full CLI flag (LLM + Docker).
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

import pytest

from helpers import BASE_URL, REAL_POLICY, env_path, run_smith
from smith.policy_agent.policy_analysis.regal.regal_finder import (
    create_regal_suggestion,
)
from smith.policy_agent.reduce_improve.detect_redundancy import write_graph_suggestion
from smith.policy_agent.scripts.parse_ast_to_graph import init_graph

pytestmark = pytest.mark.integration

# --- crafted policies -------------------------------------------------------

# Planted style issues: `= false` (should be `:=`), a braces rule with no `if`.
DIRTY_STYLE = (
    "package mcp.policies\n\n"
    "default allow = false\n\n"
    "allow {\n"
    '\tinput.name == "get_events"\n'
    "}\n"
)

# Style-clean equivalent: `:=`, `if`, canonical form.
CLEAN_STYLE = (
    "package mcp.policies\n\n"
    "import rego.v1\n\n"
    "default allow := false\n\n"
    "allow if {\n"
    '\tinput.name == "get_events"\n'
    "}\n"
)

# A rule nothing references and that `allow` does not depend on -> dead/redundant.
DEAD_RULE = (
    "package mcp.policies\n\n"
    "default allow := false\n\n"
    "allow if {\n"
    '\tinput.name == "get_events"\n'
    "}\n\n"
    "unused_helper if {\n"
    '\tinput.name == "never_referenced_tool"\n'
    "}\n"
)

# Every rule is reachable from allow -> no dead/redundant nodes.
NO_DEAD_RULE = (
    "package mcp.policies\n\n"
    "default allow := false\n\n"
    "allow if {\n"
    '\tinput.name == "get_events"\n'
    "\tapproved_topic\n"
    "}\n\n"
    "approved_topic if {\n"
    '\tinput.args.topic == "Artificial intelligence"\n'
    "}\n"
)


# ===========================================================================
# regal_suggestion — effectiveness (LLM-free)
# ===========================================================================


def _regal(policy_text, tmp_path, name="p.rego"):
    """Lint a crafted policy; return the findings text.

    Callers gate on ``requires_regal`` — ``create_regal_suggestion`` shells out
    to the ``regal`` binary, which is installed separately from ``opa``.
    """
    policy = tmp_path / name
    policy.write_text(policy_text)
    out = tmp_path / "regal_out.txt"
    return create_regal_suggestion(str(policy), str(out))


def test_regal_flags_planted_style_issues(requires_regal, tmp_path):
    findings = _regal(DIRTY_STYLE, tmp_path)
    # The specific Regal rules the planted issues should trip.
    assert "use-if" in findings, findings
    assert "use-assignment-operator" in findings, findings


def test_regal_quiet_on_clean_policy(requires_regal, tmp_path):
    # The clean policy must NOT trip the two rules the dirty one did — proving
    # regal_suggestion discriminates rather than always firing.
    findings = _regal(CLEAN_STYLE, tmp_path, name="clean.rego")
    assert "use-assignment-operator" not in findings, findings
    assert "use-if" not in findings, findings


# ===========================================================================
# duplication_suggestion — graph half effectiveness (LLM-free)
# ===========================================================================


@contextlib.contextmanager
def _cwd(path):
    """Run a block with the process cwd moved to ``path``.

    ``write_graph_suggestion`` -> ``save_unreachable_components_dot`` writes to a
    RELATIVE default ``out_path="unreachable.dot"``
    (detect_redundancy.py:18) with no way to redirect it, so it lands in whatever
    the cwd happens to be. Without this, the in-process graph tests drop a stray
    ``unreachable.dot`` into the repo root.
    """
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def _graph_suggestion(policy_text, tmp_path):
    """Run the graph redundancy analysis on a crafted policy; return its text."""
    outputs = tmp_path / "assets" / "opa" / "outputs"
    outputs.mkdir(parents=True)
    (tmp_path / "assets" / "policy.rego").write_text(policy_text)
    init_graph(
        str(outputs / "ast.json"),
        str(tmp_path / "assets") + "/",
        str(outputs / "ast.dot"),
    )
    # cwd -> tmp_path so the un-redirectable "unreachable.dot" stays in the
    # per-test temp dir instead of dirtying the working tree.
    with _cwd(tmp_path):
        return write_graph_suggestion(
            str(outputs / "ast.dot"), str(outputs / "graph_suggestion.txt")
        )


def test_graph_detects_dead_rule(requires_docker, tmp_path):
    suggestion = _graph_suggestion(DEAD_RULE, tmp_path)
    # The unreachable rule must be named as redundant.
    assert "unused_helper" in suggestion, suggestion


def test_graph_quiet_when_no_dead_rule(requires_docker, tmp_path):
    # A policy where every rule feeds allow must NOT name a redundant rule.
    # Assert only on names NO_DEAD_RULE actually defines: "unused_helper" appears
    # nowhere in this policy, so asserting its absence could never fail.
    suggestion = _graph_suggestion(NO_DEAD_RULE, tmp_path)
    assert "approved_topic" not in suggestion, suggestion


# ===========================================================================
# duplication_suggestion — full flag end to end (LLM + Docker)
# ===========================================================================


def test_duplication_flag_reports_redundancy(
    requires_llm, requires_docker, backup_file
):
    # The flag reads assets/policy.rego; copy the dead-rule policy there (session
    # backup restores it) and protect the AST/graph intermediates it writes.
    REAL_POLICY.write_text(DEAD_RULE)
    backup_file(env_path("DATA_DIR", default="assets/opa/") / "outputs")
    backup_file(Path(BASE_URL) / "unreachable.dot")

    result = run_smith("duplication_suggestion", timeout=600)
    assert result.returncode == 0, (
        f"duplication_suggestion failed (rc={result.returncode}).\n"
        f"{result.stdout[-1500:]}\n{result.stderr[-800:]}"
    )
    out = result.stdout
    # Both the labeled sections and the graph-detected dead rule appear.
    assert "redundancy suggestions" in out.lower(), out[-1500:]
    assert "unused_helper" in out, out[-1500:]
