# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the guidance -> test-case traceability behind ``--mode update``.

``smith --flag test_generation --mode update`` regenerates only the guidance that
changed since the last run. Three artifacts make that possible::

    guidance_raw_snapshot.txt   the raw guidance the last run used
                                -> describe_raw_diff() computes what the user edited
                                   and hands it to flatten as instructions

    guidance_snapshot.txt       the FLATTENED guidance the last run produced
                                -> diff_lines() against the new flattened text
                                   decides which rules are gone / new

    guidance_case_map.json      guidance line -> the case files it produced
                                -> the only way to find the cases belonging to
                                   guidance that changed

Everything is keyed on the *flattened* guidance, because that is the text the
pipeline decomposes and the text each generated case names in its ``guidance``
field.

WHY THE KEYING IS DELICATE
--------------------------
Flatten renumbers its whole output whenever a line is inserted or removed, so a
mapping key carrying ``"33. "`` breaks three ways at once: the diff (which strips
numbers) never matches it, an insertion above shifts it to ``"34. "`` and orphans
its cases, and a deletion above shifts it to ``"32. "`` so one rule is stored
twice. ``normalize`` exists to prevent that, and the round-trip test below is the
guard: a key written by ``merge_mapping`` must be findable by ``read_lines``.

FUNCTIONS UNDER TEST
--------------------
Listed — and laid out in this file — in the order an update run reaches them.

STEP 1 · ``smith.test_generation.guidance_map`` — canonical form
    ``normalize``               — bullet/number stripping, whitespace collapse,
                                  and stability across renumbering
    ``read_lines``              — blank/heading exclusion, and that it normalizes

STEP 2 · deciding what changed
    ``diff_lines``              — gone/new/unchanged over FLATTENED guidance:
                                  multiset counting, order-insensitivity
    ``diff_lines_ordered``      — gone/new/unchanged over RAW guidance:
                                  position-aware, so a moved line (e.g. two
                                  headings swapping places) counts as changed
    ``describe_raw_diff``       — the instructions handed to flatten, and the
                                  unchanged short-circuit

STEP 3 · the snapshots
    ``read_snapshot``           — absent vs empty
    ``write_snapshot``          — round-trip, and the atomic temp-file swap
    ``write_run_snapshots``     — both files, and the skip when a source is absent

STEP 4 · the mapping
    ``load_mapping``            — corrupt and wrong-shaped files degrade to empty
    ``save_mapping``            — round-trip
    ``merge_mapping``           — additive merge, guidance-keyed, attack cases
                                  without guidance skipped
    ``relocate_cases``          — following files another stage moved or deleted

STEP 5 · allocating filenames
    ``next_indices``            — append past the high-water mark, anchored prefix
                                  matching, and the ``wrong_cases/`` subtree

STEP 6 · clearing state
    ``clean_promptfoo_cases``   — prefix scope
    ``clean_generated_cases``   — whole-tree clear
    ``clear_intermediates``     — deleted, not emptied

STEP 7 · the orchestration
    ``apply_update``            — all four outcomes, selective deletion, map
                                  pruning, and survival across a renumber

NOT COVERED HERE (integration lane — see ``test_generation_update_integration.py``)
    The flatten edit prompt itself: whether a real model reproduces untouched
    lines byte-for-byte is a model property, not a code property.

Env-free: no ``.env``, no credentials, no model download, no OPA, no network.
"""

from __future__ import annotations

import json

import pytest

from smith.test_generation import guidance_map as gm

pytestmark = pytest.mark.unit


def case_tree(root, *relative_paths):
    """Create empty-envelope case files at each path, returning the root."""
    for relative in relative_paths:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"input": {"name": "x"}}), encoding="utf-8")
    return root


# ===========================================================================
# STEP 1 · canonical form
# ===========================================================================


@pytest.mark.parametrize(
    "raw",
    ["- rule text", "* rule text", "+ rule text", "1. rule text", "12) rule text"],
)
def test_every_list_marker_collapses_to_the_same_key(raw):
    assert gm.normalize(raw) == "rule text"


def test_renumbering_does_not_change_the_key():
    """The bug this function exists for.

    Flatten renumbers its entire output when a line is added or removed. If the
    number were part of the key, every rule below an edit would be orphaned.
    """
    assert gm.normalize("32. Managers may export") == gm.normalize(
        "33. Managers may export"
    )


def test_whitespace_differences_are_not_content_differences():
    assert gm.normalize("  rule   with\tgaps ") == "rule with gaps"


def test_the_rule_text_itself_is_never_altered():
    text = "A `phd_student` must set `topic` to their own `dissertation_area`."
    assert gm.normalize(f"11. {text}") == text


def test_blank_lines_and_headings_are_not_guidance():
    lines = gm.read_lines(
        "## Heading\n\n- real rule\n   \n### Another\n- second rule\n"
    )
    assert lines == ["real rule", "second rule"]


def test_read_lines_applies_the_same_normalization_as_the_map():
    """The two must agree, or no lookup ever matches (see the round-trip test)."""
    assert gm.read_lines("7. spaced   out rule") == ["spaced out rule"]


# ===========================================================================
# STEP 2 · deciding what changed
# ===========================================================================


def test_added_and_removed_lines_are_classified():
    gone, new, unchanged = gm.diff_lines(["A", "B", "C"], ["A", "C", "D"])
    assert gone == ["B"]
    assert new == ["D"]
    assert unchanged == 2


def test_an_edit_reads_as_one_removal_plus_one_addition():
    """Deliberate: an edited rule means "drop its cases, generate new ones"."""
    gone, new, _ = gm.diff_lines(["limit is 15"], ["limit is 12"])
    assert gone == ["limit is 15"]
    assert new == ["limit is 12"]


def test_reordering_flattened_guidance_is_not_a_change():
    """Flatten has already folded positional context into each entry, so
    reordering/renumbering the flattened list is not a content change."""
    gone, new, unchanged = gm.diff_lines(["A", "B", "C"], ["C", "A", "B"])
    assert (gone, new, unchanged) == ([], [], 3)


def test_duplicate_lines_are_counted_not_collapsed():
    """Two identical rules dropping to one is a deletion, not a no-op."""
    gone, new, unchanged = gm.diff_lines(["A", "A"], ["A"])
    assert gone == ["A"]
    assert new == []
    assert unchanged == 1


def test_identical_input_yields_an_empty_diff():
    assert gm.diff_lines(["A", "B"], ["A", "B"]) == ([], [], 2)


def test_ordered_diff_flags_a_pure_move():
    gone, new, unchanged = gm.diff_lines_ordered(["1", "b", "c"], ["b", "c", "1"])
    assert gone == [(1, "1")]
    assert new == [(3, "1")]
    assert unchanged == 2


def test_ordered_diff_detects_a_heading_swap():
    prev = ["## Allowed commands", "bullet1", "bullet2", "## Disallowed commands", "bullet3"]
    cur = ["## Disallowed commands", "bullet1", "bullet2", "## Allowed commands", "bullet3"]
    gone, new, unchanged = gm.diff_lines_ordered(prev, cur)
    assert {text for _, text in gone} == {"## Allowed commands", "## Disallowed commands"}
    assert {text for _, text in new} == {"## Allowed commands", "## Disallowed commands"}
    assert unchanged == 3


def test_ordered_diff_identical_input_yields_an_empty_diff():
    assert gm.diff_lines_ordered(["A", "B"], ["A", "B"]) == ([], [], 2)


def test_the_raw_diff_names_both_directions():
    described = gm.describe_raw_diff("- kept\n- dropped\n", "- kept\n- introduced\n")
    assert "ADDED OR EDITED" in described
    assert "+ [Line 2] introduced" in described
    assert "REMOVED OR REPLACED" in described
    assert "- [Line 2] dropped" in described


def test_a_deletion_only_raw_diff_still_carries_a_line_number():
    """No corresponding addition, but the removed line's position is still useful:
    it tells the flatten model which entry to drop, not just what its text was."""
    described = gm.describe_raw_diff(
        "- rule one\n- rule two\n- rule three\n", "- rule one\n- rule three\n"
    )
    assert "ADDED OR EDITED" not in described
    assert "REMOVED OR REPLACED" in described
    assert "- [Line 2] rule two" in described


def test_an_addition_only_raw_diff_still_carries_a_line_number():
    described = gm.describe_raw_diff(
        "- rule one\n- rule three\n", "- rule one\n- rule two\n- rule three\n"
    )
    assert "REMOVED OR REPLACED" not in described
    assert "ADDED OR EDITED" in described
    assert "+ [Line 2] rule two" in described


def test_an_unchanged_guidance_file_produces_no_instructions():
    """``None`` is what makes an update run stop before calling the model."""
    assert gm.describe_raw_diff("- same\n", "- same\n") is None


def test_bullet_marker_reformatting_alone_is_not_a_change():
    """Changing ``-`` to ``1.``/``2.`` with no reordering is pure formatting."""
    assert (
        gm.describe_raw_diff("- rule one\n- rule two\n", "1. rule one\n2. rule two\n")
        is None
    )


def test_reordering_the_raw_guidance_is_a_change():
    """Unlike the flattened diff, raw guidance still has positional context
    (a line's meaning can depend on what section it sits under), so swapping
    two raw lines is flagged even though neither line's own text changed."""
    described = gm.describe_raw_diff(
        "- rule one\n- rule two\n", "1. rule two\n\n2. rule one\n"
    )
    assert described is not None


# ===========================================================================
# STEP 3 · the snapshots
# ===========================================================================


def test_an_absent_snapshot_is_distinguishable_from_an_empty_one(tmp_path):
    assert gm.read_snapshot(str(tmp_path / "nope.txt")) is None
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    assert gm.read_snapshot(str(empty)) == ""


def test_a_snapshot_round_trips(tmp_path):
    target = tmp_path / "snap.txt"
    gm.write_snapshot(str(target), "1. a rule\n2. another\n")
    assert gm.read_snapshot(str(target)) == "1. a rule\n2. another\n"


def test_writing_a_snapshot_leaves_no_temp_file_behind(tmp_path):
    """The write is a temp-file swap, so a crash cannot half-write the baseline."""
    target = tmp_path / "nested" / "snap.txt"
    gm.write_snapshot(str(target), "content")
    assert target.exists()
    assert not (target.parent / "snap.txt.tmp").exists()


def test_both_run_snapshots_are_written_from_their_sources(tmp_path):
    flatten = tmp_path / "flat.txt"
    flatten.write_text("1. flattened rule\n", encoding="utf-8")
    guidance = tmp_path / "guidance.txt"
    guidance.write_text("- raw rule\n", encoding="utf-8")
    snap = tmp_path / "snap.txt"
    raw_snap = tmp_path / "raw_snap.txt"

    gm.write_run_snapshots(str(snap), str(flatten), str(raw_snap), str(guidance))

    assert snap.read_text(encoding="utf-8") == "1. flattened rule\n"
    assert raw_snap.read_text(encoding="utf-8") == "- raw rule\n"


def test_a_missing_source_is_skipped_rather_than_writing_an_empty_snapshot(tmp_path):
    """An empty baseline would make the next run think every rule was deleted."""
    snap = tmp_path / "snap.txt"
    gm.write_run_snapshots(
        str(snap), str(tmp_path / "absent.txt"), None, str(tmp_path / "absent2.txt")
    )
    assert not snap.exists()


# ===========================================================================
# STEP 4 · the mapping
# ===========================================================================


def test_a_mapping_round_trips(tmp_path):
    target = tmp_path / "map.json"
    gm.save_mapping(str(target), {"a rule": ["allow/test_case0.json"]})
    assert gm.load_mapping(str(target)) == {"a rule": ["allow/test_case0.json"]}


def test_an_absent_mapping_is_empty(tmp_path):
    assert gm.load_mapping(str(tmp_path / "nope.json")) == {}


def test_a_corrupt_mapping_degrades_to_empty(tmp_path, capsys):
    """Deleting on a guess is unrecoverable, so an unreadable map deletes nothing."""
    target = tmp_path / "map.json"
    target.write_text('{"truncated": [', encoding="utf-8")
    assert gm.load_mapping(str(target)) == {}
    assert "unreadable" in capsys.readouterr().out


def test_a_wrong_shaped_mapping_degrades_to_empty(tmp_path, capsys):
    target = tmp_path / "map.json"
    target.write_text('["not", "a", "dict"]', encoding="utf-8")
    assert gm.load_mapping(str(target)) == {}
    assert "unexpected shape" in capsys.readouterr().out


def test_merging_adds_to_the_map_without_discarding_what_is_there(tmp_path):
    """An update run must not wipe the untouched guidance's records."""
    target = tmp_path / "map.json"
    gm.save_mapping(str(target), {"old rule": ["allow/test_case0.json"]})

    gm.merge_mapping(
        str(target),
        {"allow": ["allow/test_case1.json"]},
        {"allow": ["new rule"]},
    )

    assert gm.load_mapping(str(target)) == {
        "old rule": ["allow/test_case0.json"],
        "new rule": ["allow/test_case1.json"],
    }


def test_a_key_written_by_merge_is_findable_by_the_diff(tmp_path):
    """The round-trip invariant.

    ``merge_mapping`` keys the map and ``read_lines`` produces the diff units. If
    those normalized differently, every lookup would miss and every deletion would
    silently do nothing — which is exactly the bug this guards.
    """
    target = tmp_path / "map.json"
    flattened = "33. A `phd_student` must set `topic` to their `dissertation_area`."

    gm.merge_mapping(
        str(target),
        {"allow": ["allow/test_case0.json"]},
        {"allow": [flattened]},
    )

    key = gm.read_lines(flattened)[0]
    assert key in gm.load_mapping(str(target))


def test_a_case_with_no_guidance_is_not_mapped(tmp_path):
    """Promptfoo cases carry no guidance, so they are untraceable by construction."""
    target = tmp_path / "map.json"
    gm.merge_mapping(
        str(target),
        {"promptfoo_malicious": ["disallow/promptfoo_test_case0.json"]},
        {"promptfoo_malicious": [""]},
    )
    assert gm.load_mapping(str(target)) == {}


def test_a_moved_case_is_followed_in_the_map(tmp_path):
    target = tmp_path / "map.json"
    gm.save_mapping(str(target), {"a rule": ["disallow/test_case5.json"]})

    gm.relocate_cases(
        str(target), {"disallow/test_case5.json": "allow/cv_test_case5.json"}
    )

    assert gm.load_mapping(str(target)) == {"a rule": ["allow/cv_test_case5.json"]}


def test_a_deleted_case_is_dropped_from_the_map(tmp_path):
    target = tmp_path / "map.json"
    gm.save_mapping(
        str(target), {"a rule": ["disallow/test_case5.json", "allow/test_case1.json"]}
    )

    gm.relocate_cases(str(target), {"disallow/test_case5.json": None})

    assert gm.load_mapping(str(target)) == {"a rule": ["allow/test_case1.json"]}


def test_relocating_leaves_unrelated_paths_alone(tmp_path):
    target = tmp_path / "map.json"
    gm.save_mapping(
        str(target),
        {"kept": ["allow/test_case0.json"], "moved": ["disallow/test_case1.json"]},
    )

    gm.relocate_cases(
        str(target), {"disallow/test_case1.json": "allow/cv_test_case1.json"}
    )

    mapping = gm.load_mapping(str(target))
    assert mapping["kept"] == ["allow/test_case0.json"]
    assert mapping["moved"] == ["allow/cv_test_case1.json"]


def test_relocating_nothing_is_a_no_op(tmp_path):
    target = tmp_path / "map.json"
    gm.save_mapping(str(target), {"a rule": ["allow/test_case0.json"]})
    gm.relocate_cases(str(target), {})
    assert gm.load_mapping(str(target)) == {"a rule": ["allow/test_case0.json"]}


# ===========================================================================
# STEP 5 · allocating filenames
# ===========================================================================


def test_new_cases_append_past_the_highest_index(tmp_path):
    root = case_tree(tmp_path, "allow/test_case0.json", "allow/test_case5.json")
    assert gm.next_indices(str(root) + "/")["allow"] == 6


def test_a_gap_left_by_a_deletion_is_not_reused(tmp_path):
    """max+1, never count: reusing an index would rewrite a case a report may cite."""
    root = case_tree(
        tmp_path,
        "allow/test_case0.json",
        "allow/test_case1.json",
        "allow/test_case9.json",
    )
    assert gm.next_indices(str(root) + "/")["allow"] == 10


def test_the_prefix_match_ignores_its_longer_cousins(tmp_path):
    """``disallow/`` holds three prefixes on independent sequences."""
    root = case_tree(
        tmp_path,
        "disallow/test_case2.json",
        "disallow/promptfoo_test_case77.json",
        "disallow/bypass_test_case88.json",
        "disallow/cv_test_case99.json",
    )
    starts = gm.next_indices(str(root) + "/")
    assert starts["disallow"] == 3
    assert starts["promptfoo_malicious"] == 78
    assert starts["bypass_malicious"] == 89


def test_a_case_moved_into_wrong_cases_still_reserves_its_index(tmp_path):
    """Translation relocates misrouted cases keeping the basename.

    Ignoring that subtree would reuse the index and leave two different cases
    sharing a filename, making id-based resolution ambiguous.
    """
    root = case_tree(
        tmp_path,
        "allow/test_case0.json",
        "wrong_cases/misclassified/allow/test_case7.json",
    )
    assert gm.next_indices(str(root) + "/")["allow"] == 8


def test_each_label_counts_independently(tmp_path):
    root = case_tree(tmp_path, "allow/test_case3.json", "disallow/test_case11.json")
    starts = gm.next_indices(str(root) + "/")
    assert starts["allow"] == 4
    assert starts["disallow"] == 12


def test_an_empty_tree_starts_at_zero(tmp_path):
    assert gm.next_indices(str(tmp_path) + "/") == {
        label: 0 for label in gm.CASE_TARGETS
    }


# ===========================================================================
# STEP 6 · clearing state
# ===========================================================================


def test_only_promptfoo_cases_are_cleared(tmp_path):
    """Promptfoo cases are not per-guidance, so any change invalidates the set."""
    root = case_tree(
        tmp_path,
        "disallow/promptfoo_test_case0.json",
        "disallow/promptfoo_test_case1.json",
        "disallow/test_case0.json",
        "disallow/bypass_test_case0.json",
        "allow/cv_test_case0.json",
    )
    removed = gm.clean_promptfoo_cases(str(root) + "/")

    assert removed == 2
    assert not (root / "disallow/promptfoo_test_case0.json").exists()
    assert (root / "disallow/test_case0.json").exists()
    assert (root / "disallow/bypass_test_case0.json").exists()
    assert (root / "allow/cv_test_case0.json").exists()


def test_a_cross_validated_promptfoo_case_is_cleared_too(tmp_path):
    """A moved case keeps its identity under a ``cv_`` prefix and a ``_N`` suffix.

    Matching only the pristine name would leave those behind for the scorecard to
    keep counting after the set was supposedly rebuilt.
    """
    root = case_tree(
        tmp_path,
        "disallow/promptfoo_test_case0.json",
        "disallow/cv_promptfoo_test_case1.json",
        "disallow/cv_promptfoo_test_case2_2.json",
        "disallow/test_case0.json",
    )
    removed = gm.clean_promptfoo_cases(str(root) + "/")

    assert removed == 3
    assert (root / "disallow/test_case0.json").exists()


def test_bypass_cases_are_cleared_from_both_buckets(tmp_path):
    """Bypass runs rebuild the whole set, and it spans allow/ and disallow/."""
    root = case_tree(
        tmp_path,
        "disallow/bypass_test_case0.json",
        "allow/bypass_test_case0.json",
        "allow/cv_bypass_test_case1.json",
        "allow/test_case0.json",
        "disallow/promptfoo_test_case0.json",
    )
    removed = gm.clean_bypass_cases(str(root) + "/")

    assert removed == 3
    assert (root / "allow/test_case0.json").exists()
    assert (root / "disallow/promptfoo_test_case0.json").exists()


def test_clearing_the_tree_removes_every_case_but_keeps_the_directory(tmp_path):
    """Downstream writes assume the bucket root exists."""
    root = case_tree(
        tmp_path / "tc", "allow/test_case0.json", "wrong_cases/misclassified/x.json"
    )
    removed = gm.clean_generated_cases(str(root) + "/")

    assert removed == 2
    assert root.is_dir()
    assert not any(root.rglob("*.json"))


def test_clearing_an_absent_tree_is_a_no_op(tmp_path):
    assert gm.clean_generated_cases(str(tmp_path / "absent") + "/") == 0


def test_intermediates_are_deleted_rather_than_emptied(tmp_path):
    """Downstream readers must tolerate a missing file, not just an empty list."""
    first = tmp_path / "decomp.json"
    first.write_text(json.dumps([{"guidance": "stale"}]), encoding="utf-8")

    gm.clear_intermediates(str(first), str(tmp_path / "absent.json"))

    assert not first.exists()


def test_clearing_a_non_json_intermediate_just_deletes_it(tmp_path):
    """ARES's own outputs (e.g. the attack CSV) aren't JSON-list files."""
    csv_path = tmp_path / "safety_behaviors_text_subset.csv"
    csv_path.write_text("Behavior,Category\nstale,\n", encoding="utf-8")

    gm.clear_intermediates(str(csv_path))

    assert not csv_path.exists()


# ===========================================================================
# STEP 7 · the orchestration
# ===========================================================================


@pytest.fixture
def update_env(tmp_path):
    """A prior run's state: two rules, each owning one case."""
    root = case_tree(
        tmp_path / "tc", "allow/test_case0.json", "disallow/test_case0.json"
    )
    snapshot = tmp_path / "snap.txt"
    snapshot.write_text("1. rule A\n2. rule B\n", encoding="utf-8")
    mapping = tmp_path / "map.json"
    mapping.write_text(
        json.dumps(
            {
                "rule A": ["allow/test_case0.json"],
                "rule B": ["disallow/test_case0.json"],
            }
        ),
        encoding="utf-8",
    )
    return str(root) + "/", str(snapshot), str(mapping)


def test_a_missing_snapshot_stops_the_run(tmp_path):
    outcome, subset = gm.apply_update(
        "1. anything\n",
        str(tmp_path / "absent.txt"),
        str(tmp_path / "map.json"),
        str(tmp_path) + "/",
    )
    assert outcome == gm.NO_SNAPSHOT
    assert subset is None


def test_unchanged_guidance_stops_the_run(update_env):
    root, snapshot, mapping = update_env
    outcome, subset = gm.apply_update("1. rule A\n2. rule B\n", snapshot, mapping, root)
    assert outcome == gm.UNCHANGED
    assert subset is None


def test_unchanged_guidance_touches_no_case_file(update_env):
    root, snapshot, mapping = update_env
    gm.apply_update("1. rule A\n2. rule B\n", snapshot, mapping, root)
    assert json.loads(open(mapping).read()) == {
        "rule A": ["allow/test_case0.json"],
        "rule B": ["disallow/test_case0.json"],
    }


def test_a_deletion_only_diff_reports_itself_as_such(update_env):
    root, snapshot, mapping = update_env
    outcome, subset = gm.apply_update("1. rule A\n", snapshot, mapping, root)
    assert outcome == gm.DELETED_ONLY
    assert subset is None


def test_only_the_removed_guidance_loses_its_cases(update_env, tmp_path):
    root, snapshot, mapping = update_env
    gm.apply_update("1. rule A\n", snapshot, mapping, root)

    assert (tmp_path / "tc/allow/test_case0.json").exists(), "rule A was not touched"
    assert not (tmp_path / "tc/disallow/test_case0.json").exists()


def test_removed_guidance_is_pruned_from_the_map(update_env):
    root, snapshot, mapping = update_env
    gm.apply_update("1. rule A\n", snapshot, mapping, root)
    assert json.loads(open(mapping).read()) == {"rule A": ["allow/test_case0.json"]}


def test_new_guidance_comes_back_for_decomposition(update_env):
    root, snapshot, mapping = update_env
    outcome, subset = gm.apply_update(
        "1. rule A\n2. rule B\n3. rule C\n", snapshot, mapping, root
    )
    assert outcome == gm.REGENERATE
    assert subset == "rule C"


def test_an_edited_rule_both_loses_its_cases_and_comes_back(update_env, tmp_path):
    """The delete+add pair, which is how an edit is represented."""
    root, snapshot, mapping = update_env
    outcome, subset = gm.apply_update(
        "1. rule A\n2. rule B revised\n", snapshot, mapping, root
    )

    assert outcome == gm.REGENERATE
    assert subset == "rule B revised"
    assert not (tmp_path / "tc/disallow/test_case0.json").exists()
    assert "rule B" not in json.loads(open(mapping).read())


def test_a_renumbered_rule_is_not_mistaken_for_a_change(update_env, tmp_path):
    """Removing rule A renumbers rule B from 2 to 1.

    Without number-stripping this would read as "both rules changed" and delete
    rule B's cases too.
    """
    root, snapshot, mapping = update_env
    outcome, _ = gm.apply_update("1. rule B\n", snapshot, mapping, root)

    assert outcome == gm.DELETED_ONLY
    assert (tmp_path / "tc/disallow/test_case0.json").exists(), "rule B was renumbered"
    assert json.loads(open(mapping).read()) == {"rule B": ["disallow/test_case0.json"]}


def test_guidance_the_map_never_covered_is_reported_not_guessed(update_env, capsys):
    """Cases generated before the map existed cannot be located; say so."""
    root, snapshot, mapping = update_env
    with open(mapping, "w") as handle:
        json.dump({"rule A": ["allow/test_case0.json"]}, handle)

    gm.apply_update("1. rule A\n", snapshot, mapping, root)

    assert "no recorded cases for" in capsys.readouterr().out
