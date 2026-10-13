# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Offline tests for deterministic Phase A implementation inspection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from smith.tools.guidance_reconciliation import ReconciliationError
from smith.tools.security_analysis_inspection import inspect_architecture

pytestmark = pytest.mark.unit


def _definitions(path: Path, *, required_limit: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "source": "python server.py",
                "tools": [
                    {
                        "name": "search",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "limit": {"type": "integer"},
                            },
                            "required": (
                                ["query", "limit"] if required_limit else ["query"]
                            ),
                        },
                    }
                ],
            }
        )
    )
    return path


def test_inspection_selects_bounded_implementation_hops_and_compares_signatures(
    tmp_path: Path,
):
    target = tmp_path / "agent"
    target.mkdir()
    (target / "server.py").write_text(
        "from helper import execute\n"
        "mcp = FastMCP('sample')\n"
        "@mcp.tool()\n"
        "def search(query: str, limit: int = 10):\n"
        "    return execute(query, limit)\n"
    )
    (target / "helper.py").write_text(
        "from service import lookup\n"
        "def execute(query, limit):\n"
        "    return lookup(query, limit)\n"
    )
    (target / "service.py").write_text(
        "from third_hop import remote_lookup\n"
        "def lookup(query, limit):\n"
        "    return remote_lookup(query, limit)\n"
    )
    (target / "third_hop.py").write_text(
        "def remote_lookup(query, limit):\n"
        "    return {'query': query, 'limit': limit}\n"
    )
    tests = target / "tests"
    tests.mkdir()
    (tests / "test_server.py").write_text("FastMCP search policy authorization")
    definitions = _definitions(target / "smith/tool_definitions.json")
    output = target / "smith/guidelines-security-analysis/architecture_inspection.json"

    result = inspect_architecture(target, definitions, output)

    report = json.loads(output.read_text())
    selected = {item["path"]: item for item in report["selected_files"]}
    assert result.startswith("Security analysis inspection PASS")
    assert set(selected) == {"server.py", "helper.py", "service.py"}
    assert selected["server.py"]["hop"] == 0
    assert selected["helper.py"]["hop"] == 1
    assert selected["service.py"]["hop"] == 2
    assert report["unresolved_relevant_paths"] == ["third_hop.py"]
    assert report["limits"] == {"max_files": 20, "max_reference_hops": 2}
    assert report["tool_signature_comparison"]["status"] == "PASS"


def test_inspection_writes_report_then_fails_on_proven_signature_mismatch(
    tmp_path: Path,
):
    target = tmp_path / "agent"
    target.mkdir()
    (target / "server.py").write_text(
        "mcp = FastMCP('sample')\n"
        "@mcp.tool()\n"
        "def search(query: str, limit: int = 10):\n"
        "    return []\n"
    )
    definitions = _definitions(
        target / "smith/tool_definitions.json", required_limit=True
    )
    output = target / "inspection.json"

    with pytest.raises(ReconciliationError, match="inspection FAIL"):
        inspect_architecture(target, definitions, output)

    comparison = json.loads(output.read_text())["tool_signature_comparison"]
    assert comparison["status"] == "FAIL"
    assert comparison["incompatible"] == [
        {
            "tool": "search",
            "differences": ["limit: required=False (expected True)"],
        }
    ]


def test_inspection_enforces_file_budget_and_reports_overflow(tmp_path: Path):
    target = tmp_path / "agent"
    target.mkdir()
    for number in range(25):
        (target / f"module_{number:02d}.py").write_text(
            f"mcp = FastMCP('sample-{number}')\n"
        )
    definitions = target / "smith/tool_definitions.json"
    definitions.parent.mkdir()
    definitions.write_text(json.dumps({"tools": []}))
    output = target / "inspection.json"

    inspect_architecture(target, definitions, output)

    report = json.loads(output.read_text())
    assert len(report["selected_files"]) == 20
    assert len(report["unresolved_relevant_paths"]) == 5
