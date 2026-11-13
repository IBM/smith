# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Load the OWASP catalog and write the per-phase snapshots the analysis reads."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from typing import Any

from smith.tools.guidance_reconciliation import ReconciliationError

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "owasp_10_ai_catalog.json"
CATALOG_IDS = tuple(f"ASI{number:02d}" for number in range(1, 11))
SNAPSHOT_SCHEMA = "owasp-catalog-snapshot-v1"
SNAPSHOT_FIELDS = {
    "C": ("id", "name", "description", "threat_aliases", "attack_scenarios"),
    "D": (
        "id",
        "name",
        "impact",
        "business_impact",
        "mitigations",
        "mitigation_steps",
        "source_url",
    ),
}


@dataclass(frozen=True)
class Catalog:
    path: Path
    sha256: str
    framework: str | None
    version: str | None
    threats: tuple[dict[str, Any], ...]

    @property
    def scenario_counts(self) -> dict[str, int]:
        return {entry["id"]: len(entry["attack_scenarios"]) for entry in self.threats}


def load_catalog(path: Path) -> Catalog:
    """Parse the catalog once and hash exactly the bytes that were parsed."""
    if not path.is_file():
        raise ReconciliationError(f"OWASP catalog is missing: {path}")
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
        threats = data["threats"]
        if not isinstance(threats, list) or not all(
            isinstance(entry, dict) for entry in threats
        ):
            raise TypeError("threats must be a list of objects")
        threats = tuple(threats)
        ids = [entry["id"] for entry in threats]
        if not all(isinstance(asi, str) for asi in ids):
            raise TypeError("threat IDs must be strings")
        empty = [
            entry["id"]
            for entry in threats
            if not isinstance(entry.get("attack_scenarios"), list)
            or not entry["attack_scenarios"]
        ]
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        AttributeError,
    ) as exc:
        raise ReconciliationError(f"OWASP catalog is malformed: {path}: {exc}") from exc
    if sorted(ids) != list(CATALOG_IDS):
        raise ReconciliationError(
            f"OWASP catalog is malformed: {path}: threat IDs must be "
            "ASI01 through ASI10 exactly once"
        )
    if empty:
        raise ReconciliationError(
            f"OWASP catalog is malformed: {path}: entries without attack "
            f"scenarios: {', '.join(empty)}"
        )
    return Catalog(
        path=path,
        sha256=hashlib.sha256(raw).hexdigest(),
        framework=data.get("framework"),
        version=data.get("version"),
        threats=threats,
    )


def snapshot_path(analysis_dir: Path, phase: str) -> Path:
    return analysis_dir / f"owasp_catalog_{phase}.json"


def build_snapshot(
    catalog: Catalog, phase: str, applicable: list[str] | None = None
) -> dict[str, Any]:
    """Project the catalog onto the fields one phase may read.

    Phase C gets discovery fields for every category and no mitigation keys.
    Phase D gets mitigation fields for exactly the ``applicable`` categories.
    """
    if phase == "C":
        entries = list(catalog.threats)
    elif phase == "D":
        wanted = set(applicable or [])
        unknown = sorted(wanted - set(CATALOG_IDS))
        if unknown:
            raise ReconciliationError(
                f"unknown OWASP catalog categories: {', '.join(unknown)}"
            )
        entries = [entry for entry in catalog.threats if entry["id"] in wanted]
    else:
        raise ReconciliationError("catalog snapshots exist only for Phases C and D")
    return {
        "schema": SNAPSHOT_SCHEMA,
        "phase": phase,
        "catalog": {
            "framework": catalog.framework,
            "version": catalog.version,
            "sha256": catalog.sha256,
        },
        "threats": [
            {field: entry.get(field) for field in SNAPSHOT_FIELDS[phase]}
            for entry in entries
        ],
    }


def write_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    """Write deterministically, so the same catalog yields the same bytes."""
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def snapshot_drift(expected: dict[str, Any], actual: Any) -> str | None:
    """Name the first item where a snapshot differs from the current projection.

    The whole snapshot is checked, since all of it reaches the model: unexpected
    keys, non-object rows and duplicate IDs are drift, not skipped. The recorded
    catalog hash is informational, so an edit outside a phase's slice does not
    invalidate it.
    """
    if (
        not isinstance(actual, dict)
        or actual.get("schema") != expected["schema"]
        or actual.get("phase") != expected["phase"]
        or not isinstance(actual.get("threats"), list)
    ):
        return "snapshot format"
    unexpected = sorted(set(actual) - set(expected))
    if unexpected:
        return f"unexpected snapshot keys: {', '.join(unexpected)}"
    header = actual.get("catalog")
    if not isinstance(header, dict) or set(header) != set(expected["catalog"]):
        return "snapshot catalog header"
    for field in ("framework", "version"):
        if header[field] != expected["catalog"][field]:
            return f"catalog {field}"
    rows = actual["threats"]
    if not all(isinstance(row, dict) for row in rows):
        return "snapshot rows must be objects"
    ids = [row.get("id") for row in rows]
    if not all(isinstance(asi, str) for asi in ids):
        return "snapshot row IDs must be strings"
    duplicates = sorted({asi for asi in ids if ids.count(asi) > 1})
    if duplicates:
        return f"duplicate snapshot rows: {', '.join(duplicates)}"
    current = {entry["id"]: entry for entry in expected["threats"]}
    recorded = dict(zip(ids, rows))
    if list(current) != ids:
        return (
            f"category set (snapshot has {', '.join(ids) or 'none'}; "
            f"expected {', '.join(current) or 'none'})"
        )
    for asi, entry in current.items():
        other = recorded[asi]
        for field, value in entry.items():
            if other.get(field) == value:
                continue
            if field == "attack_scenarios" and isinstance(other.get(field), list):
                for index, (now, then) in enumerate(
                    zip_longest(value, other[field]), 1
                ):
                    if now != then:
                        return f"{asi}#{index}"
            return f"{asi} {field}"
        if set(other) != set(entry):
            return f"{asi} fields"
    return None
