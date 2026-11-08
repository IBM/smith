# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the OWASP catalog loader and per-phase snapshots.

``smith --flag security_analysis_checkpoint`` reads the catalog through
``smith.tools.security_catalog``: ``--prepare`` writes the snapshot a phase
reads, and the checkpoint compares that snapshot with the current catalog.

FUNCTIONS UNDER TEST
--------------------
``load_catalog``      — one read, hash of the parsed bytes, strict structure,
                        the existing missing/malformed messages
``build_snapshot``    — Phase C discovery fields; Phase D applicable mitigations
``write_snapshot``    — byte-identical output for the same catalog
``snapshot_drift``    — names the first changed scenario, field, or category

Checkpoint wiring (prepare, freshness gate, provenance, merge guard) is covered
in ``test_security_analysis_checkpoint_unit.py``.

Env-free: no ``.env``, no credentials, no model download, no network.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from smith.tools.guidance_reconciliation import ReconciliationError
from smith.tools.security_catalog import (
    CATALOG_IDS,
    CATALOG_PATH,
    build_snapshot,
    load_catalog,
    snapshot_drift,
    write_snapshot,
)

pytestmark = pytest.mark.unit


def catalog_data() -> dict:
    return {
        "framework": "OWASP Top 10 for Agentic AI Security",
        "version": "0.1",
        "threats": [
            {
                "id": asi,
                "name": f"Category {asi}",
                "description": f"{asi} description",
                "threat_aliases": [f"{asi} alias"],
                "attack_scenarios": [f"{asi} first", f"{asi} second"],
                "impact": f"{asi} impact",
                "business_impact": f"{asi} business impact",
                "mitigations": [f"{asi} mitigation"],
                "mitigation_steps": [f"{asi} step"],
                "source_url": f"https://example.test/{asi}",
            }
            for asi in CATALOG_IDS
        ],
    }


def write(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data))
    return path


# --- load_catalog -------------------------------------------------------------


def test_load_catalog_hashes_the_bytes_it_parsed(tmp_path: Path):
    path = write(tmp_path / "catalog.json", catalog_data())

    catalog = load_catalog(path)

    assert catalog.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert catalog.scenario_counts == {asi: 2 for asi in CATALOG_IDS}
    assert (catalog.framework, catalog.version) == (
        "OWASP Top 10 for Agentic AI Security",
        "0.1",
    )


def test_shipped_catalog_loads_with_61_scenarios():
    catalog = load_catalog(CATALOG_PATH)

    assert [entry["id"] for entry in catalog.threats] == list(CATALOG_IDS)
    assert sum(catalog.scenario_counts.values()) == 61


def test_missing_catalog_keeps_the_existing_message(tmp_path: Path):
    with pytest.raises(ReconciliationError, match="OWASP catalog is missing"):
        load_catalog(tmp_path / "absent.json")


@pytest.mark.parametrize(
    "content",
    ["not json", "[]", '{"threats": [{"name": "no id"}]}'],
    ids=["invalid-json", "not-an-object", "entry-without-id"],
)
def test_malformed_catalog_keeps_the_existing_message(tmp_path: Path, content):
    path = tmp_path / "catalog.json"
    path.write_text(content)

    with pytest.raises(ReconciliationError, match="OWASP catalog is malformed"):
        load_catalog(path)


def test_duplicate_or_missing_ids_are_rejected(tmp_path: Path):
    data = catalog_data()
    data["threats"][9]["id"] = "ASI01"

    with pytest.raises(ReconciliationError, match="ASI01 through ASI10 exactly once"):
        load_catalog(write(tmp_path / "catalog.json", data))


def test_entry_without_scenarios_is_rejected(tmp_path: Path):
    """Previously this silently removed the ASI from mandatory coverage."""
    data = catalog_data()
    data["threats"][3]["attack_scenarios"] = []

    with pytest.raises(ReconciliationError, match="without attack scenarios: ASI04"):
        load_catalog(write(tmp_path / "catalog.json", data))


# --- build_snapshot / write_snapshot ------------------------------------------


def test_phase_c_snapshot_has_no_mitigation_or_impact_keys(tmp_path: Path):
    catalog = load_catalog(write(tmp_path / "catalog.json", catalog_data()))

    snapshot = build_snapshot(catalog, "C")

    assert [entry["id"] for entry in snapshot["threats"]] == list(CATALOG_IDS)
    assert set(snapshot["threats"][0]) == {
        "id",
        "name",
        "description",
        "threat_aliases",
        "attack_scenarios",
    }
    assert snapshot["catalog"]["sha256"] == catalog.sha256


def test_phase_d_snapshot_holds_only_requested_categories(tmp_path: Path):
    catalog = load_catalog(write(tmp_path / "catalog.json", catalog_data()))

    snapshot = build_snapshot(catalog, "D", ["ASI06", "ASI02"])

    assert [entry["id"] for entry in snapshot["threats"]] == ["ASI02", "ASI06"], (
        "categories keep catalog order regardless of how they were requested"
    )
    assert "attack_scenarios" not in snapshot["threats"][0]
    assert snapshot["threats"][0]["mitigations"] == ["ASI02 mitigation"]


def test_phase_d_snapshot_rejects_unknown_categories(tmp_path: Path):
    catalog = load_catalog(write(tmp_path / "catalog.json", catalog_data()))

    with pytest.raises(ReconciliationError, match="ASI11"):
        build_snapshot(catalog, "D", ["ASI11"])


def test_snapshots_exist_only_for_phases_c_and_d(tmp_path: Path):
    catalog = load_catalog(write(tmp_path / "catalog.json", catalog_data()))

    with pytest.raises(ReconciliationError, match="only for Phases C and D"):
        build_snapshot(catalog, "B")


def test_written_snapshot_is_byte_identical_across_runs(tmp_path: Path):
    catalog = load_catalog(write(tmp_path / "catalog.json", catalog_data()))
    first, second = tmp_path / "first.json", tmp_path / "second.json"

    write_snapshot(first, build_snapshot(catalog, "C"))
    write_snapshot(second, build_snapshot(load_catalog(catalog.path), "C"))

    assert first.read_bytes() == second.read_bytes()
    assert not first.with_suffix(".json.tmp").exists()


# --- snapshot_drift -----------------------------------------------------------


def drift_after(tmp_path: Path, phase: str, edit, applicable=None) -> str | None:
    """Snapshot the catalog, apply ``edit``, and report the drift."""
    data = catalog_data()
    before = build_snapshot(
        load_catalog(write(tmp_path / "before.json", data)), phase, applicable
    )
    recorded = json.loads(json.dumps(before))
    edited = copy.deepcopy(data)
    edit(edited)
    after = build_snapshot(
        load_catalog(write(tmp_path / "after.json", edited)), phase, applicable
    )
    return snapshot_drift(after, recorded)


def test_unchanged_catalog_has_no_drift(tmp_path: Path):
    assert drift_after(tmp_path, "C", lambda data: None) is None


def test_reworded_scenario_is_named_by_its_scenario_id(tmp_path: Path):
    def reword(data):
        data["threats"][2]["attack_scenarios"][1] = "ASI03 sec0nd"

    assert drift_after(tmp_path, "C", reword) == "ASI03#2"


def test_added_scenario_is_named_by_its_new_index(tmp_path: Path):
    def add(data):
        data["threats"][0]["attack_scenarios"].append("ASI01 third")

    assert drift_after(tmp_path, "C", add) == "ASI01#3"


def test_changed_field_is_named(tmp_path: Path):
    def edit(data):
        data["threats"][4]["mitigation_steps"] = ["changed"]

    assert drift_after(tmp_path, "D", edit, ["ASI05"]) == "ASI05 mitigation_steps"


def test_edits_outside_a_phase_slice_are_not_drift(tmp_path: Path):
    def edit(data):
        data["threats"][0]["mitigations"] = ["changed"]
        data["threats"][5]["mitigations"] = ["changed"]

    assert drift_after(tmp_path, "C", edit) is None, "Phase C cannot see mitigations"
    assert drift_after(tmp_path, "D", edit, ["ASI02"]) is None


def test_changed_category_set_is_reported(tmp_path: Path):
    catalog = load_catalog(write(tmp_path / "catalog.json", catalog_data()))
    recorded = build_snapshot(catalog, "D", ["ASI01"])

    drift = snapshot_drift(build_snapshot(catalog, "D", ["ASI01", "ASI02"]), recorded)

    assert drift == "category set (snapshot has ASI01; expected ASI01, ASI02)"


@pytest.mark.parametrize(
    "recorded",
    [None, [], {"schema": "other"}, {"schema": "owasp-catalog-snapshot-v1"}],
    ids=["null", "list", "wrong-schema", "no-threats"],
)
def test_unreadable_snapshot_shape_is_drift(tmp_path: Path, recorded):
    catalog = load_catalog(write(tmp_path / "catalog.json", catalog_data()))

    assert snapshot_drift(build_snapshot(catalog, "C"), recorded) == "snapshot format"
