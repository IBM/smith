# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the functions behind ``smith --flag red_suggestion``.

Red suggestion is the refinement step that reads ``policy_testing``'s failures and
groups them, so a human fixes a *cluster* of related failures rather than one case
at a time::

    read_files(scorecard/fp.txt)   case-file paths -> the prompts they contain
    read_files(scorecard/fn.txt)   likewise for false negatives
    SentenceTransformer.encode     each prompt -> a vector
    DBSCAN(eps, min_samples)       vectors -> cluster labels
    _ordered_cluster_labels        noise group sorted last, then renumbered
    -> cluster_results.txt

No LLM, no agent, no OPA: the inputs are files written by ``policy_testing`` and
the only model is a local sentence embedder.

SCOPE: WHY THIS NEEDS A UNIT LANE
---------------------------------
Two reasons, and the first is a hard requirement:

1. ``cluster_commands`` constructs ``SentenceTransformer("all-MiniLM-L6-v2")``,
   which **downloads model weights**. The guide's unit lane forbids that, so the
   embedder is faked — which also makes DBSCAN's output deterministic instead of
   depending on where real embeddings happen to fall.
2. Three behaviours are impractical to reach through a live run:
   * ``read_files``' **three-way format fallback** (old ``original_command``, new
     ``extensions.agent.input``, or a stringified input) — a compatibility shim,
     where a real run only ever exercises whichever format the current fixtures use.
   * The **noise group's renumbering**: DBSCAN labels unclustered points ``-1``, and
     that must display as the final cluster number, never as "Cluster -1".
   * The **FP/FN cluster-number offset**, which stops the two independent
     renumberings from colliding.

Everything between the faked embedder and the written file — the reading, the real
DBSCAN, the grouping and the report text — runs for real.

FUNCTIONS UNDER TEST
--------------------
Listed — and laid out in this file — in the order the flag executes them.

STEP 1 · ``smith.policy_agent.red_feedback.red_feedback``
    ``read_files``              — the three input formats, and the
                                  command -> case-file mapping the report needs

STEP 2 · clustering and report assembly
    ``_ordered_cluster_labels`` — the noise group sorts last
    ``cluster_commands``        — both sections, the renumbering, the FP/FN
                                  offset, empty inputs, and the written artifact

Also covered
    ``process_command_format``  — the 3-line trace format its caller depends on

NOT COVERED HERE (integration lane — see ``test_red_suggestion_integration.py``)
    That the real ``fp.txt``/``fn.txt`` written by ``score_card.sh`` is in the shape
    ``read_files`` expects, and that the real MiniLM + DBSCAN at ``eps=0.3``
    actually group near-duplicate prompts together.

Deliberately absent: ``read_records_command`` and ``find_files_recursively``. They
parse OpenTelemetry traces from a hardcoded ``./trace/`` directory for an
``NL2Kubectl`` agent, and no CLI flag reaches them — see the pinned test at the end.

Env-free: ``SentenceTransformer`` is patched, so no weights are downloaded.
"""

from __future__ import annotations

import json
import re

import pytest

from smith.policy_agent.red_feedback import red_feedback as rf_mod
from smith.policy_agent.red_feedback.red_feedback import (
    _ordered_cluster_labels,
    cluster_commands,
    process_command_format,
    read_files,
)

from fakes import FakeEmbedder

pytestmark = pytest.mark.unit


#: Distinct vectors, keyed by a substring of the prompt. Points sharing a vector
#: are at cosine distance 0 and so always cluster; different vectors are
#: orthogonal (distance 1.0) and so never do at eps=0.3. That makes every
#: grouping below a property of the code, not of an embedding model.
VECTORS = {
    "alpha": [1, 0, 0, 0, 0, 0, 0, 0],
    "beta": [0, 1, 0, 0, 0, 0, 0, 0],
    "gamma": [0, 0, 1, 0, 0, 0, 0, 0],
    "delta": [0, 0, 0, 1, 0, 0, 0, 0],
}


@pytest.fixture
def scorecard(unit_env):
    """A scorecard directory with helpers to stage ``fp.txt`` / ``fn.txt``.

    ``cluster_commands`` builds its paths by **string concatenation**
    (``test_path + "fp.txt"``), so the trailing separator is part of the contract.
    """
    root = unit_env.root / "references" / "scorecard"
    root.mkdir(parents=True, exist_ok=True)
    cases = unit_env.root / "references" / "test_cases"
    cases.mkdir(parents=True, exist_ok=True)

    class Scorecard:
        path = str(root) + "/"
        results = root / "cluster_results.txt"

        def case(self, filename, prompt):
            """A case file in the modern envelope shape."""
            target = cases / filename
            target.write_text(
                json.dumps(
                    {"input": {"extensions": {"agent": {"input": prompt}}}}, indent=4
                )
            )
            return target

        def stage(self, fp=(), fn=()):
            """Write fp.txt/fn.txt listing one case-file path per line."""
            for name, prompts in (("fp.txt", fp), ("fn.txt", fn)):
                paths = [
                    str(self.case(f"{name.split('.')[0]}_{i}.json", p))
                    for i, p in enumerate(prompts)
                ]
                (root / name).write_text("\n".join(paths) + ("\n" if paths else ""))

    return Scorecard()


def _fake_embedder(monkeypatch, vectors=VECTORS):
    fake = FakeEmbedder(vectors=vectors)
    monkeypatch.setattr(rf_mod, "SentenceTransformer", fake)
    return fake


def _cluster_numbers(lines) -> list:
    """Every cluster number the report displays, in order."""
    return re.findall(r"Cluster (-?\d+)", "\n".join(lines))


# ===========================================================================
# STEP 1 · read_files — getting the prompt out of a case file
# ===========================================================================

def test_the_listing_is_read_as_one_case_path_per_line(unit_env):
    # This is the contract with score_card.sh, which writes fp.txt/fn.txt. Lines
    # are stripped, so a trailing newline must not become an empty path.
    first = unit_env.root / "a.json"
    second = unit_env.root / "b.json"
    for path, prompt in ((first, "first prompt"), (second, "second prompt")):
        path.write_text(
            json.dumps({"input": {"extensions": {"agent": {"input": prompt}}}})
        )
    listing = unit_env.root / "fp.txt"
    listing.write_text(f"{first}\n{second}\n")

    commands, mapping = read_files(str(listing), {})

    assert commands == ["first prompt", "second prompt"]
    assert len(mapping) == 2


# ===========================================================================
# STEP 2 · _ordered_cluster_labels — the noise group sorts last
# ===========================================================================


@pytest.mark.parametrize(
    "labels,expected",
    [
        ({0: [], 1: [], -1: []}, [0, 1, -1]),
        ({2: [], -1: [], 0: []}, [0, 2, -1]),
        ({-1: []}, [-1]),
        ({0: [], 1: []}, [0, 1]),
    ],
    ids=["noise-last", "unsorted-input", "noise-only", "no-noise"],
)
def test_the_noise_group_is_ordered_after_the_real_clusters(labels, expected):
    assert _ordered_cluster_labels(labels) == expected


# ===========================================================================
# STEP 2 · cluster_commands — grouping, numbering, and the artifact
# ===========================================================================


def test_similar_failures_are_grouped_and_dissimilar_ones_are_not(
    scorecard, monkeypatch
):
    # The point of the flag: a reviewer fixes one cluster, not three cases. The
    # vectors make "alpha" prompts identical and "gamma" orthogonal, so this
    # asserts the grouping code rather than an embedding model's judgement.
    scorecard.stage(fp=["alpha one", "alpha two", "gamma lone"])
    _fake_embedder(monkeypatch)

    lines = cluster_commands(str(scorecard.results), scorecard.path, 0.3, 2)

    text = "\n".join(lines)
    assert "Benign commands that should be allowed:" in text
    # Two groups: the alpha pair, and gamma alone as noise.
    assert _cluster_numbers(lines) == ["0", "1"]
    alpha_block = text.split("Cluster 1:")[0]
    assert "alpha one" in alpha_block and "alpha two" in alpha_block
    assert "gamma lone" not in alpha_block


def test_the_noise_group_is_never_displayed_as_cluster_minus_one(
    scorecard, monkeypatch
):
    scorecard.stage(fp=["alpha solo", "beta solo", "gamma solo"])
    _fake_embedder(monkeypatch)

    lines = cluster_commands(str(scorecard.results), scorecard.path, 0.3, 2)

    numbers = _cluster_numbers(lines)
    assert numbers, "no clusters were reported at all"
    assert all(int(n) >= 0 for n in numbers), f"a negative cluster id leaked: {numbers}"


def test_false_negative_clusters_are_numbered_after_the_false_positive_ones(
    scorecard, monkeypatch
):
    scorecard.stage(fp=["alpha one", "alpha two"], fn=["beta one", "beta two"])
    _fake_embedder(monkeypatch)

    lines = cluster_commands(str(scorecard.results), scorecard.path, 0.3, 2)

    text = "\n".join(lines)
    assert "Benign commands that should be allowed:" in text
    assert "Malicious commands that should not get allowed:" in text
    # One FP cluster (0), so the FN cluster continues at 1 — no duplicates.
    numbers = _cluster_numbers(lines)
    assert numbers == ["0", "1"]
    assert len(numbers) == len(set(numbers)), f"duplicate cluster ids: {numbers}"
    # And the sections are not swapped.
    assert text.index("Benign") < text.index("Malicious")


def test_every_clustered_case_names_the_file_it_came_from(scorecard, monkeypatch):
    # The file path is the actionable part: a reviewer has to open the case to fix
    # it. A cluster listing prompts without paths would be unusable.
    scorecard.stage(fp=["alpha one", "alpha two"])
    _fake_embedder(monkeypatch)

    lines = cluster_commands(str(scorecard.results), scorecard.path, 0.3, 2)

    text = "\n".join(lines)
    assert text.count("File path: ") == 2
    for line in lines:
        if line.startswith("Test Case "):
            path = line.split("File path: ")[1]
            assert path.endswith(".json"), f"not a case file: {path!r}"


def test_the_report_is_written_to_disk(scorecard, monkeypatch):
    # The return value is what the CLI prints; the file is what a reviewer keeps.
    scorecard.stage(fp=["alpha one", "alpha two"])
    _fake_embedder(monkeypatch)

    lines = cluster_commands(str(scorecard.results), scorecard.path, 0.3, 2)

    assert scorecard.results.read_text() == "\n".join(lines)


def test_only_the_populated_section_appears(scorecard, monkeypatch, capsys):
    # A policy with no false positives is a good outcome, not an error. The report
    # must say so by omitting the section rather than printing an empty header.
    scorecard.stage(fp=[], fn=["beta one", "beta two"])
    _fake_embedder(monkeypatch)

    lines = cluster_commands(str(scorecard.results), scorecard.path, 0.3, 2)

    text = "\n".join(lines)
    assert "Benign commands" not in text
    assert "Malicious commands that should not get allowed:" in text
    # With no FP clusters the offset is zero, so FN numbering starts at 0.
    assert _cluster_numbers(lines) == ["0"]
    assert "no false positives found" in capsys.readouterr().out


def test_a_clean_scorecard_produces_an_empty_report_without_embedding_anything(
    scorecard, monkeypatch, capsys
):
    scorecard.stage(fp=[], fn=[])
    fake = _fake_embedder(monkeypatch)

    lines = cluster_commands(str(scorecard.results), scorecard.path, 0.3, 2)

    assert lines == []
    assert scorecard.results.read_text() == ""
    assert not fake.loaded, "the embedder was asked to encode an empty failure set"
    out = capsys.readouterr().out
    assert "no false positives found" in out and "no false negatives found" in out


def test_min_samples_controls_what_counts_as_a_cluster(scorecard, monkeypatch):
    # The tunable a user reaches for (CLUSTER_MIN_SAMPLES). At 3, a pair is no
    # longer a cluster and falls into noise — still reported, just not grouped.
    scorecard.stage(fp=["alpha one", "alpha two"])
    _fake_embedder(monkeypatch)

    lines = cluster_commands(str(scorecard.results), scorecard.path, 0.3, 3)

    # Still exactly one displayed group (the noise group, renumbered to 0), and
    # both cases still listed — the parameter changes grouping, not coverage.
    assert _cluster_numbers(lines) == ["0"]
    text = "\n".join(lines)
    assert "alpha one" in text and "alpha two" in text


# ===========================================================================
# Dead code, pinned
# ===========================================================================


@pytest.mark.parametrize(
    "command,expected",
    [
        ("```\nkubectl get pods\n```", "kubectl get pods"),
        ("kubectl get pods", ""),
        ("a\nb\nc\nd", ""),
        ("", ""),
    ],
    ids=["fenced-3-line", "single-line", "four-line", "empty"],
)
def test_only_a_three_line_command_block_yields_its_middle_line(command, expected):
    # Pinned: anything not exactly 3 lines yields "" rather than raising. So a
    # differently-shaped trace silently contributes an empty command.
    assert process_command_format(command) == expected
