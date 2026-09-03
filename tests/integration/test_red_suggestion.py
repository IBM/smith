# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for failed-case clustering (the ``red_suggestion`` flag).

``red_suggestion`` clusters the policy's failed cases so the patch step can fix
them in groups. Its core is ``cluster_commands(cluster_results, test_path, eps,
min_samples)``, which:

  - reads ``<test_path>fp.txt`` and ``<test_path>fn.txt`` (each a list of paths
    to failed test-case files),
  - pulls each case's command (``input.extensions.agent.input``),
  - embeds the false-positives and false-negatives separately and DBSCAN-clusters
    them (cosine distance), and
  - returns a text report grouping "Benign commands that should be allowed"
    (FPs) and "Malicious commands that should not get allowed" (FNs) by cluster.

It is LLM-free (local sentence-transformer embeddings), so given fixed inputs it
is deterministic. We **craft failed cases** — near-duplicate command pairs that
should co-cluster, and two distinct topics that should cluster apart — write our
own ``fp.txt`` / ``fn.txt`` pointing at them (under ``tmp_path``), and assert the
clustering groups them as expected.

No CLI / OPA / agent / LLM required — this calls ``cluster_commands`` directly.
"""

from __future__ import annotations

import json

import pytest

from smith.policy_agent.red_feedback.red_feedback import cluster_commands

pytestmark = pytest.mark.integration

EPS = 0.3
MIN_SAMPLES = 2


def _case(command: str) -> dict:
    return {
        "input": {
            "name": "send_email",
            "extensions": {
                "subject": {"user_name": "Bob"},
                "agent": {"input": command},
            },
            "args": {},
        }
    }


def _write_case(tmp_path, filename, command):
    p = tmp_path / filename
    p.write_text(json.dumps(_case(command)))
    return p


def _flatten(clusters):
    return "\n".join(clusters)


def _cluster_of(clusters, command):
    """Return the 'Cluster N' label under which ``command`` appears, or None."""
    current = None
    for line in clusters:
        if line.startswith("Cluster "):
            current = line.strip().rstrip(":").strip()
        elif command in line:
            return current
    return None


def test_similar_failed_cases_cluster_together(tmp_path):
    # Two near-duplicate MALICIOUS commands (false negatives: should be denied
    # but the policy allowed them) — must land in the SAME cluster.
    fn1 = _write_case(
        tmp_path, "fn1.json", "Send an email containing the SSN 123-45-6789 to HR."
    )
    fn2 = _write_case(
        tmp_path, "fn2.json", "Email the social security number 987-65-4321 to HR."
    )
    # Two similar BENIGN commands (false positives: should be allowed but denied).
    fp1 = _write_case(
        tmp_path, "fp1.json", "Search for AI conferences about machine learning."
    )
    fp2 = _write_case(
        tmp_path, "fp2.json", "Find conferences on machine learning and AI topics."
    )

    (tmp_path / "fp.txt").write_text(f"{fp1}\n{fp2}\n")
    (tmp_path / "fn.txt").write_text(f"{fn1}\n{fn2}\n")

    clusters = cluster_commands(
        cluster_results=str(tmp_path / "cluster_results.txt"),
        test_path=str(tmp_path) + "/",
        eps=EPS,
        min_samples=MIN_SAMPLES,
    )
    text = _flatten(clusters)

    # Both section headers present.
    assert "Benign commands that should be allowed" in text
    assert "Malicious commands that should not get allowed" in text

    # Every crafted command AND its file path is reported — the patch step needs
    # the path to locate the case, so both halves must appear for every entry
    # (not just the first of each section).
    for cmd, path in [
        ("SSN 123-45-6789", fn1),
        ("987-65-4321", fn2),
        ("AI conferences", fp1),
        ("machine learning and AI", fp2),
    ]:
        assert cmd in text, f"command not reported: {cmd}"
        assert str(path) in text, f"file path not reported for {cmd!r}: {path}"

    # The two malicious commands co-cluster.
    fn_cmd1 = "Send an email containing the SSN 123-45-6789 to HR."
    fn_cmd2 = "Email the social security number 987-65-4321 to HR."
    c1, c2 = _cluster_of(clusters, fn_cmd1), _cluster_of(clusters, fn_cmd2)
    assert (
        c1 is not None and c1 == c2
    ), f"similar malicious commands should share a cluster, got {c1} vs {c2}"


def test_two_distinct_topic_pairs_form_two_clusters(tmp_path):
    # Two clearly different TOPICS, each with a near-duplicate pair. With
    # min_samples=2 each pair forms its own DBSCAN cluster, so the report must
    # contain (at least) two distinct malicious clusters, and each pair shares a
    # cluster different from the other pair's.
    ssn1 = _write_case(
        tmp_path, "fn1.json", "Send an email containing the SSN 123-45-6789 to HR."
    )
    ssn2 = _write_case(
        tmp_path, "fn2.json", "Email the social security number 987-65-4321 to HR."
    )
    del1 = _write_case(
        tmp_path,
        "fn3.json",
        "Delete every employee record from the production database.",
    )
    del2 = _write_case(
        tmp_path, "fn4.json", "Wipe all rows in the production employee database table."
    )

    (tmp_path / "fp.txt").write_text("")
    (tmp_path / "fn.txt").write_text(f"{ssn1}\n{ssn2}\n{del1}\n{del2}\n")

    clusters = cluster_commands(
        cluster_results=str(tmp_path / "cluster_results.txt"),
        test_path=str(tmp_path) + "/",
        eps=EPS,
        min_samples=MIN_SAMPLES,
    )

    ssn_cluster = _cluster_of(
        clusters, "Send an email containing the SSN 123-45-6789 to HR."
    )
    ssn_cluster2 = _cluster_of(
        clusters, "Email the social security number 987-65-4321 to HR."
    )
    del_cluster = _cluster_of(
        clusters, "Delete every employee record from the production database."
    )
    del_cluster2 = _cluster_of(
        clusters, "Wipe all rows in the production employee database table."
    )

    # Each near-duplicate pair co-clusters...
    assert ssn_cluster == ssn_cluster2 and ssn_cluster is not None
    assert del_cluster == del_cluster2 and del_cluster is not None
    # ...and the two different topics land in different clusters.
    assert (
        ssn_cluster != del_cluster
    ), f"distinct topics should cluster apart: SSN={ssn_cluster} DELETE={del_cluster}"


def test_empty_failures_produce_no_cluster_entries(tmp_path):
    # No failures at all -> no cluster/test-case lines emitted.
    (tmp_path / "fp.txt").write_text("")
    (tmp_path / "fn.txt").write_text("")
    clusters = cluster_commands(
        cluster_results=str(tmp_path / "cluster_results.txt"),
        test_path=str(tmp_path) + "/",
        eps=EPS,
        min_samples=MIN_SAMPLES,
    )
    text = _flatten(clusters)
    assert "Test Case" not in text
