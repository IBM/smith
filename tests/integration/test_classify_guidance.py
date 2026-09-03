# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit test for guidance-line classification (the ``classify_guidance`` flag).

We craft several agent shapes (a multi-tool HR/employee agent, a car-price
agent) and guidance lines with known expected mappings, then assert the LLM
classification matches:
  - a line naming a specific action maps to that tool,
  - a cross-cutting "before any write" line maps to multiple write tools,
  - a definitional/contextual line maps to no tool (empty).

Assertions check membership + validity (results are a subset of the defined
tools) rather than exact-equality where the LLM has reasonable latitude; the
empty-mapping cases are asserted exactly. Requires a real LLM (``requires_llm``).
"""

from __future__ import annotations

import os

import pytest

from smith.tools.classify_guidance_lines import classify_guidance_lines

pytestmark = pytest.mark.integration


def _tooldefs(*names_and_descs) -> dict:
    """Build a tool_definitions doc from (name, description) pairs."""
    return {
        "tools": [{"name": n, "description": d} for n, d in names_and_descs],
        "source": "unit-test",
        "transport": "none",
    }


def _classify(guidance_text: str, tool_definitions: dict):
    """Call the real classifier with the configured LLM; return index->result."""
    results = classify_guidance_lines(
        os.getenv("OPENAI_API_KEY"),
        os.getenv("OPENAI_BASE_URL"),
        os.getenv("MODEL_SONNET"),
        float(os.getenv("TEMP", "0.2")),
        float(os.getenv("TOP_P", "0.9")),
        guidance_text,
        tool_definitions,
    )
    return {r["index"]: r for r in results}


# --- Agent shape A: multi-tool HR / employee directory ---------------------

HR_TOOLS = _tooldefs(
    ("get_employee", "Fetch a single employee record by id."),
    ("update_employee", "Modify fields on an existing employee record."),
    ("set_passport", "Set or update an employee's passport details."),
    ("list_departments", "List all departments in the org."),
)


def test_hr_specific_action_maps_to_its_tool(requires_llm):
    guidance = "HR staff may update an employee's passport information."
    res = _classify(guidance, HR_TOOLS)
    tools = res[0]["tools"]
    assert "set_passport" in tools, f"expected set_passport, got {tools} ({res[0]})"
    # Only real tool names may appear.
    assert set(tools) <= {
        "get_employee",
        "update_employee",
        "set_passport",
        "list_departments",
    }


def test_hr_definitional_line_maps_to_no_tool(requires_llm):
    guidance = "A manager is an employee who has at least one direct report."
    res = _classify(guidance, HR_TOOLS)
    assert res[0]["tools"] == [], (
        f"definition should map to no tool, got {res[0]['tools']} "
        f"(reason={res[0].get('reason')})"
    )


def test_hr_cross_cutting_write_rule_maps_to_write_tools(requires_llm):
    guidance = "Any change that writes to an employee record requires manager approval."
    res = _classify(guidance, HR_TOOLS)
    tools = set(res[0]["tools"])
    # Must include at least one of the write tools; must not include read-only ones only.
    assert tools & {"update_employee", "set_passport"}, (
        f"write rule should map to write tools, got {tools} "
        f"(reason={res[0].get('reason')})"
    )
    assert tools <= {
        "get_employee",
        "update_employee",
        "set_passport",
        "list_departments",
    }


# --- Agent shape B: car-price lookup ---------------------------------------

CAR_TOOLS = _tooldefs(
    ("get_car_brands", "List all supported car brands."),
    ("search_car_price", "Look up the price for a given car brand."),
    (
        "get_vehicles_by_type",
        "List vehicles of a given type (cars, motorcycles, trucks).",
    ),
)


def test_car_price_lookup_maps_to_search(requires_llm):
    guidance = "Users may look up the price of a car only for supported brands."
    res = _classify(guidance, CAR_TOOLS)
    tools = set(res[0]["tools"])
    assert "search_car_price" in tools, f"expected search_car_price, got {tools}"
    assert tools <= {"get_car_brands", "search_car_price", "get_vehicles_by_type"}


def test_multiline_guidance_indices_and_shape(requires_llm):
    # Two rules + one blank line: indices are source-line based, blanks dropped.
    guidance = "\n".join(
        [
            "1. Users may list the available car brands.",
            "",
            "2. Listing vehicles by type is allowed for everyone.",
        ]
    )
    res = _classify(guidance, CAR_TOOLS)
    # Two non-blank rule lines classified.
    assert len(res) == 2, f"expected 2 classified lines, got {list(res)}"
    for item in res.values():
        assert set(item["tools"]) <= {
            "get_car_brands",
            "search_car_price",
            "get_vehicles_by_type",
        }
        assert "reason" in item
