# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Embedding index over the OWASP catalog, for ranking and cross-category search.

Two exact-cosine indexes, stored as NumPy matrices: one over attack scenarios
(Phase C), one over mitigations and mitigation steps (Phase D). They are kept
apart so a scenario query can never return a mitigation.

``rank`` reorders a given set and never drops an item. ``search`` returns a
bounded number of additional candidates from outside a given set of
categories. Nothing here is wired into the phase workflow yet; the CLI exposes
both for tuning and for the ordering evaluation in the design document.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from sentence_transformers import SentenceTransformer

from smith.tools.guidance_reconciliation import ReconciliationError
from smith.tools.security_catalog import Catalog, load_catalog

INDEX_SCHEMA = "owasp-catalog-index-v1"
DEFAULT_MODEL = "all-MiniLM-L6-v2"
DEFAULT_PARAMS = {"top_k": 8, "max_items": 120}
CORPORA = ("scenarios", "mitigations")

Corpus = Literal["scenarios", "mitigations"]


@dataclass(frozen=True)
class Item:
    id: str
    asi: str
    text: str


@dataclass(frozen=True)
class Hit:
    id: str
    asi: str
    score: float
    query: int
    text: str


def catalog_items(catalog: Catalog, corpus: Corpus) -> list[Item]:
    """Every indexable item of one corpus, in catalog order, with canonical IDs.

    Scenario IDs (``ASI03#4``) match the ``Scenario Coverage`` column.
    Mitigation IDs are ``ASI03/mit#2`` and ``ASI03/step#5``; like scenario IDs
    they are positional, so read them together with the catalog hash.
    """
    items: list[Item] = []
    for entry in catalog.threats:
        asi = entry["id"]
        if corpus == "scenarios":
            items.extend(
                Item(f"{asi}#{number}", asi, text)
                for number, text in enumerate(entry["attack_scenarios"], 1)
            )
        else:
            for field, kind in (("mitigations", "mit"), ("mitigation_steps", "step")):
                items.extend(
                    Item(f"{asi}/{kind}#{number}", asi, text)
                    for number, text in enumerate(entry.get(field) or [], 1)
                )
    return items


def embedding_text(catalog: Catalog, item: Item, prefix: bool) -> str:
    """Text embedded for one item. The prefix format is open question 1."""
    if not prefix:
        return item.text
    name = next(entry["name"] for entry in catalog.threats if entry["id"] == item.asi)
    return f"{name}: {item.text}"


def _normalized(vectors) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix[np.newaxis, :]
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def build_index(
    catalog_path: Path,
    index_dir: Path,
    *,
    model_id: str = DEFAULT_MODEL,
    prefix: bool = True,
) -> str:
    """Embed both corpora and write ``manifest.json`` plus one ``.npz`` each."""
    catalog = load_catalog(catalog_path)
    encoder = SentenceTransformer(model_id)
    index_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for corpus in CORPORA:
        items = catalog_items(catalog, corpus)
        vectors = _normalized(
            encoder.encode([embedding_text(catalog, item, prefix) for item in items])
        )
        temporary = index_dir / f"{corpus}.tmp.npz"
        np.savez(
            temporary,
            ids=np.array([item.id for item in items]),
            vectors=vectors,
        )
        temporary.replace(index_dir / f"{corpus}.npz")
        counts[corpus] = len(items)
    manifest = {
        "schema": INDEX_SCHEMA,
        "catalog_sha256": catalog.sha256,
        "model_id": model_id,
        "prefix": prefix,
        "dimensions": int(vectors.shape[1]),
        "counts": counts,
        "params": DEFAULT_PARAMS,
    }
    temporary = index_dir / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    temporary.replace(index_dir / "manifest.json")
    return (
        f"Built OWASP catalog index: {counts['scenarios']} scenarios, "
        f"{counts['mitigations']} mitigation items ({model_id}, "
        f"prefix {'on' if prefix else 'off'}) -> {index_dir}"
    )


def validate_index(index_dir: Path, catalog: Catalog) -> dict | None:
    """Return the manifest, ``None`` if absent, or raise if stale.

    Absent and stale need different handling: a missing index falls back to
    catalog order, while an index describing other content must not be used.
    """
    manifest_path = index_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReconciliationError(f"OWASP catalog index manifest is malformed: {exc}")
    rebuild = "rebuild with smith --flag security_catalog_index --build"
    if not isinstance(manifest, dict) or manifest.get("schema") != INDEX_SCHEMA:
        raise ReconciliationError(
            f"OWASP catalog index has an unsupported schema; {rebuild}"
        )
    if manifest.get("catalog_sha256") != catalog.sha256:
        raise ReconciliationError(
            f"OWASP catalog index was built from a different catalog; {rebuild}"
        )
    for corpus in CORPORA:
        expected = len(catalog_items(catalog, corpus))
        path = index_dir / f"{corpus}.npz"
        if not path.is_file():
            raise ReconciliationError(
                f"OWASP catalog index is missing {path.name}; {rebuild}"
            )
        with np.load(path) as stored:
            ids = list(stored["ids"])
            shape = stored["vectors"].shape
        if (
            manifest.get("counts", {}).get(corpus) != expected
            or len(ids) != expected
            or shape != (expected, manifest.get("dimensions"))
            or ids != [item.id for item in catalog_items(catalog, corpus)]
        ):
            raise ReconciliationError(
                f"OWASP catalog index {corpus} does not match the catalog; {rebuild}"
            )
    return manifest


class CatalogIndex:
    """Loaded, validated index plus the encoder that built it."""

    def __init__(
        self,
        catalog: Catalog,
        manifest: dict,
        vectors: dict[str, np.ndarray],
        encoder,
    ):
        self.catalog = catalog
        self.manifest = manifest
        self._vectors = vectors
        self._items = {corpus: catalog_items(catalog, corpus) for corpus in CORPORA}
        self._encoder = encoder

    @classmethod
    def load(cls, index_dir: Path, catalog: Catalog) -> CatalogIndex | None:
        """Load a fresh index, return ``None`` if absent, raise if stale."""
        manifest = validate_index(index_dir, catalog)
        if manifest is None:
            return None
        vectors = {}
        for corpus in CORPORA:
            with np.load(index_dir / f"{corpus}.npz") as stored:
                vectors[corpus] = stored["vectors"].astype(np.float32)
        return cls(
            catalog, manifest, vectors, SentenceTransformer(manifest["model_id"])
        )

    def _corpus_items(self, corpus: Corpus) -> list[Item]:
        if corpus not in CORPORA:
            raise ReconciliationError(f"unknown corpus {corpus!r}")
        return self._items[corpus]

    def _scores(self, queries: list[str], corpus: Corpus) -> np.ndarray:
        return _normalized(self._encoder.encode(list(queries))) @ (
            self._vectors[corpus].T
        )

    def rank(
        self, queries: list[str], *, corpus: Corpus, restrict_asi=()
    ) -> list[list[Hit]]:
        """Order the corpus (or the ``restrict_asi`` part of it) per query.

        Order-only: every query gets the same set of items, highest score first,
        ties in catalog order. Nothing is dropped and no threshold applies.
        """
        items = self._corpus_items(corpus)
        keep = [
            position
            for position, item in enumerate(items)
            if not restrict_asi or item.asi in set(restrict_asi)
        ]
        scores = self._scores(queries, corpus)
        groups = []
        for query, row in enumerate(scores):
            ordered = sorted(keep, key=lambda position: (-row[position], position))
            groups.append(
                [
                    Hit(items[p].id, items[p].asi, float(row[p]), query, items[p].text)
                    for p in ordered
                ]
            )
        return groups

    def search(
        self,
        queries: list[str],
        *,
        corpus: Corpus,
        top_k: int | None = None,
        max_items: int | None = None,
        exclude_asi=(),
    ) -> list[Hit]:
        """Bounded additional candidates from outside ``exclude_asi``.

        Per query, take the ``top_k`` best items outside the excluded categories,
        skipping any whose text already appears inside them: the catalog repeats
        many mitigation texts across categories, and re-adding text the baseline
        already holds would add nothing. Deduplicate by ID keeping the best score,
        then cap the total at ``max_items``. Every query that has a candidate
        keeps its best one even past the cap, so a few high-scoring queries
        cannot spend the whole budget.
        """
        params = self.manifest.get("params", DEFAULT_PARAMS)
        top_k = params["top_k"] if top_k is None else top_k
        max_items = params["max_items"] if max_items is None else max_items
        if top_k < 1 or max_items < 1:
            raise ReconciliationError("top_k and max_items must be at least 1")
        items = self._corpus_items(corpus)
        excluded = set(exclude_asi)
        baseline_texts = {item.text for item in items if item.asi in excluded}
        eligible = [
            position
            for position, item in enumerate(items)
            if item.asi not in excluded and item.text not in baseline_texts
        ]
        scores = self._scores(queries, corpus)
        per_query: list[list[Hit]] = []
        for query, row in enumerate(scores):
            ordered = sorted(eligible, key=lambda position: (-row[position], position))
            per_query.append(
                [
                    Hit(items[p].id, items[p].asi, float(row[p]), query, items[p].text)
                    for p in ordered[:top_k]
                ]
            )
        best: dict[str, Hit] = {}
        for hits in per_query:
            for hit in hits:
                if hit.id not in best or hit.score > best[hit.id].score:
                    best[hit.id] = hit
        chosen: dict[str, Hit] = {}
        for hits in per_query:
            if hits:
                top = best[hits[0].id]
                chosen.setdefault(top.id, top)
        for hit in sorted(best.values(), key=lambda hit: (-hit.score, hit.id)):
            if len(chosen) >= max_items:
                break
            chosen.setdefault(hit.id, hit)
        return sorted(chosen.values(), key=lambda hit: (hit.query, -hit.score))


def describe_index(index_dir: Path, catalog_path: Path) -> str:
    catalog = load_catalog(catalog_path)
    try:
        manifest = validate_index(index_dir, catalog)
    except ReconciliationError as exc:
        return f"OWASP catalog index: STALE ({exc})"
    if manifest is None:
        return (
            f"OWASP catalog index: ABSENT at {index_dir}; phases use catalog order. "
            "Build with smith --flag security_catalog_index --build"
        )
    counts = manifest["counts"]
    return (
        f"OWASP catalog index: FRESH at {index_dir}\n"
        f"- catalog sha256: {manifest['catalog_sha256']}\n"
        f"- model: {manifest['model_id']} ({manifest['dimensions']} dimensions), "
        f"prefix {'on' if manifest['prefix'] else 'off'}\n"
        f"- items: {counts['scenarios']} scenarios, "
        f"{counts['mitigations']} mitigation items\n"
        f"- params: {json.dumps(manifest['params'], sort_keys=True)}"
    )


def query_index(
    index_dir: Path,
    catalog_path: Path,
    query: str,
    phase: str,
    *,
    restrict_asi=(),
    limit: int = 10,
) -> str:
    """Ranked and searched hits for one query, formatted for tuning by hand."""
    catalog = load_catalog(catalog_path)
    index = CatalogIndex.load(index_dir, catalog)
    if index is None:
        raise ReconciliationError(
            f"OWASP catalog index is absent at {index_dir}; build it with "
            "smith --flag security_catalog_index --build"
        )
    corpus: Corpus = "scenarios" if phase == "C" else "mitigations"
    lines = [f"Query: {query}", f"Corpus: {corpus} (Phase {phase})", ""]
    ranked = index.rank([query], corpus=corpus, restrict_asi=restrict_asi)[0]
    scope = ", ".join(restrict_asi) if restrict_asi else "all categories"
    lines.append(f"Ranked ({scope}; top {min(limit, len(ranked))} of {len(ranked)}):")
    lines.extend(_hit_line(hit) for hit in ranked[:limit])
    if phase == "D" and restrict_asi:
        added = index.search([query], corpus=corpus, exclude_asi=restrict_asi)
        lines.extend(["", f"Cross-category candidates ({len(added)}):"])
        lines.extend([_hit_line(hit) for hit in added] or ["  none"])
    return "\n".join(lines)


def _hit_line(hit: Hit) -> str:
    text = hit.text if len(hit.text) <= 100 else hit.text[:97] + "..."
    return f"  {hit.score:6.3f}  {hit.id:<14} {text}"
