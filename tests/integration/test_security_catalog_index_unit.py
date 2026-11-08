# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the functions behind ``smith --flag security_catalog_index``.

The flag builds, inspects and queries an embedding index over the OWASP
catalog::

    --build              catalog -> SentenceTransformer -> scenarios.npz,
                         mitigations.npz, manifest.json
    (no option)          manifest + freshness against the current catalog
    --query --phase C|D  rank within --asi; Phase D also searches the rest

FUNCTIONS UNDER TEST
--------------------
STEP 0 · ``smith.cli``
    dispatch                  — build / status / query branches, error exit

STEP 1 · ``build_index``      — counts 61 / 300, unit-norm vectors,
                                byte-identical rebuild, prefix on and off

    ``catalog_items``         — canonical IDs, catalog order, corpora apart
    ``embedding_text``        — category-name prefix on and off

STEP 2 · ``validate_index`` / ``describe_index``
                              — absent returns None; stale catalog, model
                                output, or schema raises

STEP 3 · ``CatalogIndex.rank``   — order-only: a permutation of the same IDs
         ``CatalogIndex.search`` — ``top_k``, ``max_items``, ≥1 per query,
                                   ``exclude_asi``, dedupe by max score,
                                   skips text repeated inside the baseline
         ``query_index``         — formatted output, absent index error

NOT COVERED HERE (integration lane — see
``test_security_catalog_index_integration.py``)
    That the real MiniLM embeddings rank a query's own subject matter first.

Env-free: ``SentenceTransformer`` is patched, so no weights are downloaded.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from fakes import FakeEmbedder
from smith import cli as cli_mod
from smith.tools import security_catalog_index as index_mod
from smith.tools.guidance_reconciliation import ReconciliationError
from smith.tools.security_catalog import CATALOG_IDS, CATALOG_PATH, load_catalog
from smith.tools.security_catalog_index import (
    CatalogIndex,
    build_index,
    catalog_items,
    describe_index,
    embedding_text,
    query_index,
    validate_index,
)

pytestmark = pytest.mark.unit


def catalog_data() -> dict:
    """Ten categories; ASI02 and ASI03 share one mitigation text on purpose."""
    threats = []
    for asi in CATALOG_IDS:
        threats.append(
            {
                "id": asi,
                "name": f"Category {asi}",
                "attack_scenarios": [f"{asi} scenario one", f"{asi} scenario two"],
                "mitigations": [f"{asi} mitigation"],
                "mitigation_steps": [f"{asi} step"],
            }
        )
    threats[2]["mitigation_steps"].append("shared step text")
    threats[1]["mitigation_steps"].append("shared step text")
    return {"threats": threats}


def write_catalog(path: Path, data: dict | None = None) -> Path:
    path.write_text(json.dumps(data or catalog_data()))
    return path


@pytest.fixture
def embedder(monkeypatch):
    fake = FakeEmbedder(dim=8)
    monkeypatch.setattr(index_mod, "SentenceTransformer", fake)
    return fake


@pytest.fixture
def built(tmp_path: Path, embedder) -> dict:
    catalog = write_catalog(tmp_path / "catalog.json")
    index_dir = tmp_path / "index"
    build_index(catalog, index_dir)
    return {"catalog": catalog, "index_dir": index_dir, "embedder": embedder}


def loaded_index(built: dict, vectors: dict[str, list[float]]) -> CatalogIndex:
    """An index whose stored vectors and query vectors are both chosen."""
    catalog = load_catalog(built["catalog"])
    stored = {}
    for corpus in index_mod.CORPORA:
        items = catalog_items(catalog, corpus)
        stored[corpus] = index_mod._normalized(
            [vectors.get(item.id, [0.0] * 7 + [1.0]) for item in items]
        )
    manifest = validate_index(built["index_dir"], catalog)
    return CatalogIndex(catalog, manifest, stored, built["embedder"])


# --- STEP 0 · cli dispatch ----------------------------------------------------


def run_cli(monkeypatch, tmp_path: Path, *args: str) -> int:
    monkeypatch.setenv("BASE_URL", str(tmp_path))
    monkeypatch.setenv("SECURITY_CATALOG_INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setattr(sys, "argv", ["smith", "--flag", "security_catalog_index"])
    sys.argv.extend(args)
    with pytest.raises(SystemExit) as exit_info:
        cli_mod.main()
    return exit_info.value.code


def test_cli_reports_an_absent_index_without_loading_a_model(
    monkeypatch, tmp_path: Path, capsys
):
    # Deliberately unpatched: the status path must never construct an encoder.
    assert run_cli(monkeypatch, tmp_path) == 0
    assert "ABSENT" in capsys.readouterr().out


def test_cli_builds_then_reports_fresh(monkeypatch, tmp_path: Path, embedder, capsys):
    assert run_cli(monkeypatch, tmp_path, "--build") == 0
    assert "61 scenarios, 300 mitigation items" in capsys.readouterr().out

    assert run_cli(monkeypatch, tmp_path) == 0
    assert "FRESH" in capsys.readouterr().out


def test_cli_query_needs_phase_c_or_d(monkeypatch, tmp_path: Path, capsys):
    assert run_cli(monkeypatch, tmp_path, "--query", "anything") == 1
    assert "--query requires --phase C or D" in capsys.readouterr().err


def test_cli_query_prints_ranked_and_cross_category_hits(
    monkeypatch, tmp_path: Path, embedder, capsys
):
    run_cli(monkeypatch, tmp_path, "--build")
    capsys.readouterr()

    code = run_cli(
        monkeypatch, tmp_path, "--query", "goal hijack", "--phase", "D", "--asi", "asi01"
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "Ranked (ASI01; top 10 of 19)" in out
    assert "Cross-category candidates (8):" in out


# --- STEP 1 · build_index -----------------------------------------------------


def test_shipped_catalog_ids_are_canonical_and_complete():
    catalog = load_catalog(CATALOG_PATH)

    scenarios = catalog_items(catalog, "scenarios")
    mitigations = catalog_items(catalog, "mitigations")

    assert (len(scenarios), len(mitigations)) == (61, 300)
    assert scenarios[0].id == "ASI01#1"
    assert mitigations[0].id == "ASI01/mit#1"
    assert mitigations[8].id == "ASI01/step#1", "steps follow an entry's mitigations"
    assert len({item.id for item in scenarios + mitigations}) == 361


def test_embedding_text_prefix_is_switchable(tmp_path: Path):
    catalog = load_catalog(write_catalog(tmp_path / "catalog.json"))
    item = catalog_items(catalog, "mitigations")[0]

    assert embedding_text(catalog, item, prefix=True) == (
        "Category ASI01: ASI01 mitigation"
    )
    assert embedding_text(catalog, item, prefix=False) == "ASI01 mitigation"


def test_build_writes_unit_norm_vectors_and_manifest(built):
    index_dir = built["index_dir"]
    manifest = json.loads((index_dir / "manifest.json").read_text())
    catalog = load_catalog(built["catalog"])

    assert manifest["catalog_sha256"] == catalog.sha256
    assert manifest["counts"] == {"scenarios": 20, "mitigations": 22}
    assert manifest["prefix"] is True
    for corpus in ("scenarios", "mitigations"):
        with np.load(index_dir / f"{corpus}.npz") as stored:
            norms = np.linalg.norm(stored["vectors"], axis=1)
            assert np.allclose(norms, 1.0)
    assert not list(index_dir.glob("*.tmp*")), "atomic writes leave no temp files"


def test_build_embeds_prefixed_text_by_default_and_raw_text_on_request(
    tmp_path: Path, embedder
):
    catalog = write_catalog(tmp_path / "catalog.json")

    build_index(catalog, tmp_path / "on")
    build_index(catalog, tmp_path / "off", prefix=False)

    prefixed, raw = embedder.encoded[1], embedder.encoded[3]
    assert prefixed[0] == "Category ASI01: ASI01 mitigation"
    assert raw[0] == "ASI01 mitigation"


def test_rebuild_is_byte_identical(built):
    digest = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in built["index_dir"].iterdir()
    }

    build_index(built["catalog"], built["index_dir"])

    assert digest == {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in built["index_dir"].iterdir()
    }


# --- STEP 2 · validate_index / describe_index ---------------------------------


def test_absent_index_is_none_not_an_error(tmp_path: Path):
    catalog = load_catalog(write_catalog(tmp_path / "catalog.json"))

    assert validate_index(tmp_path / "missing", catalog) is None
    assert CatalogIndex.load(tmp_path / "missing", catalog) is None


def test_index_from_another_catalog_fails_closed(built):
    data = catalog_data()
    data["threats"][0]["mitigations"] = ["edited after build"]
    edited = load_catalog(write_catalog(built["catalog"], data))

    with pytest.raises(ReconciliationError, match="different catalog; rebuild"):
        validate_index(built["index_dir"], edited)
    assert "STALE" in describe_index(built["index_dir"], built["catalog"])


def test_index_with_wrong_item_count_fails_closed(built):
    path = built["index_dir"] / "mitigations.npz"
    with np.load(path) as stored:
        ids, vectors = stored["ids"][:-1], stored["vectors"][:-1]
    np.savez(path, ids=ids, vectors=vectors)
    catalog = load_catalog(built["catalog"])

    with pytest.raises(ReconciliationError, match="mitigations does not match"):
        validate_index(built["index_dir"], catalog)


def test_index_with_unknown_schema_fails_closed(built):
    manifest_path = built["index_dir"] / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["schema"] = "owasp-catalog-index-v0"
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ReconciliationError, match="unsupported schema"):
        validate_index(built["index_dir"], load_catalog(built["catalog"]))


# --- STEP 3 · rank / search / query_index -------------------------------------

HIJACK = [1.0, 0, 0, 0, 0, 0, 0, 0]
PRIVILEGE = [0, 1.0, 0, 0, 0, 0, 0, 0]


def test_rank_is_a_permutation_of_the_same_ids(built):
    index = loaded_index(built, {"ASI01/step#1": HIJACK})
    baseline = {
        item.id
        for item in catalog_items(index.catalog, "mitigations")
        if item.asi in {"ASI01", "ASI02"}
    }
    built["embedder"]._vectors = {"hijack": HIJACK, "privilege": PRIVILEGE}

    groups = index.rank(
        ["hijack query", "privilege query"],
        corpus="mitigations",
        restrict_asi=("ASI01", "ASI02"),
    )

    for hits in groups:
        assert Counter(hit.id for hit in hits) == Counter(baseline), (
            "rank may reorder the baseline but must never add or drop items"
        )
    assert groups[0][0].id == "ASI01/step#1"


def test_rank_breaks_ties_in_catalog_order(built):
    index = loaded_index(built, {})
    built["embedder"]._vectors = {"tie": [0, 0, 0, 0, 0, 0, 0, 1.0]}

    hits = index.rank(["tie"], corpus="scenarios")[0]

    assert [hit.id for hit in hits[:3]] == ["ASI01#1", "ASI01#2", "ASI02#1"]


def test_scenario_and_mitigation_corpora_never_mix(built):
    index = loaded_index(built, {})

    scenario_ids = {hit.id for hit in index.rank(["q"], corpus="scenarios")[0]}
    mitigation_ids = {hit.id for hit in index.rank(["q"], corpus="mitigations")[0]}

    assert all("#" in item and "/" not in item for item in scenario_ids)
    assert all("/" in item for item in mitigation_ids)
    with pytest.raises(ReconciliationError, match="unknown corpus"):
        index.rank(["q"], corpus="guidance")


def test_search_respects_top_k_and_exclusions(built):
    index = loaded_index(built, {})

    hits = index.search(
        ["q"], corpus="mitigations", top_k=3, exclude_asi=("ASI01", "ASI02")
    )

    assert len(hits) == 3
    assert not {hit.asi for hit in hits} & {"ASI01", "ASI02"}


def test_search_skips_text_the_baseline_already_holds(built):
    """The real catalog repeats 72 mitigation texts across categories."""
    index = loaded_index(built, {"ASI03/step#2": HIJACK})
    built["embedder"]._vectors = {"hijack": HIJACK}

    hits = index.search(
        ["hijack"], corpus="mitigations", top_k=30, exclude_asi=("ASI02",)
    )

    assert "ASI03/step#2" not in {hit.id for hit in hits}, (
        "ASI03/step#2 repeats ASI02/step#2 word for word, so it adds nothing"
    )


def test_search_keeps_one_hit_per_query_even_past_max_items(built):
    index = loaded_index(built, {"ASI05/mit#1": HIJACK, "ASI07/mit#1": PRIVILEGE})
    built["embedder"]._vectors = {"hijack": HIJACK, "privilege": PRIVILEGE}

    hits = index.search(
        ["hijack", "privilege"], corpus="mitigations", top_k=4, max_items=1
    )

    assert {hit.id for hit in hits} == {"ASI05/mit#1", "ASI07/mit#1"}


def test_search_dedupes_by_id_keeping_the_best_score(built):
    index = loaded_index(built, {"ASI05/mit#1": [1.0, 1.0, 0, 0, 0, 0, 0, 0]})
    built["embedder"]._vectors = {"hijack": HIJACK, "both": [1.0, 1.0, 0, 0, 0, 0, 0, 0]}

    hits = index.search(["hijack", "both"], corpus="mitigations", top_k=2)

    matches = [hit for hit in hits if hit.id == "ASI05/mit#1"]
    assert len(matches) == 1
    assert matches[0].query == 1 and matches[0].score == pytest.approx(1.0)


def test_search_rejects_non_positive_bounds(built):
    index = loaded_index(built, {})

    with pytest.raises(ReconciliationError, match="at least 1"):
        index.search(["q"], corpus="mitigations", top_k=0)


def test_query_index_without_an_index_names_the_build_command(tmp_path: Path):
    catalog = write_catalog(tmp_path / "catalog.json")

    with pytest.raises(ReconciliationError, match="--build"):
        query_index(tmp_path / "missing", catalog, "q", "C")


def test_query_index_phase_c_has_no_cross_category_section(built):
    out = query_index(built["index_dir"], built["catalog"], "q", "C")

    assert "Corpus: scenarios (Phase C)" in out
    assert "Ranked (all categories; top 10 of 20)" in out
    assert "Cross-category" not in out
