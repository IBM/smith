# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration test for ``smith --flag get_mcp_parameter``.

This flag extracts MCP tool definitions from the running MCP server and writes
them to ``<TARGET_AGENT_PATH>/smith/tool_definitions.json``. It is LLM-free, so
given a fixed MCP server the result is deterministic.

We assert the extracted contract against a **hardcoded expectation** derived
from the example MCP server's source.

Requires the example agent / its stdio MCP server (``agent_server``); no LLM.
"""

from __future__ import annotations

import json
import os

import pytest

from helpers import EXAMPLE, REFERENCES, env_rel, load_json, run_smith

pytestmark = pytest.mark.integration

TOOL_DEFS = EXAMPLE / "smith" / "tool_definitions.json"
SESSION_CONFIG = REFERENCES / "__test_session_config__.json"

EXPECTED_CONTRACT = {
    "get_events": {
        "keywords": ("string", True),
        "topic": ("string", True),
        "limit": ("integer", False),
    }
}


def _mcp_env(session_config_rel: str | None = None) -> dict:
    env = dict(os.environ)
    rel = env_rel(EXAMPLE)
    env.update(
        {
            "TARGET_AGENT_PATH": rel,
            "MCP_TRANSPORT": "stdio",
            "MCP_COMMAND": "python",
            "MCP_ARGS": "server.py",
            "MCP_CWD": rel,
            "SESSION_CONFIG_FILE": (
                session_config_rel or "references/__no_session_config__.json"
            ),
        }
    )
    return env


def _write_session_config(backup_file, **payload) -> str:
    """Write a session config to a protected throwaway path; return its rel path. """
    backup_file(SESSION_CONFIG)
    SESSION_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    SESSION_CONFIG.write_text(json.dumps(payload, indent=2))
    return env_rel(SESSION_CONFIG)


def _tool_contract(defs: dict) -> dict:
    """Reduce a tool_definitions doc to the stable contract we compare on:

    {tool_name: {param_name: (type, required)}}

    Ignores incidental/metadata fields (source, transport, descriptions,
    input_schema titles) that aren't part of the tool interface.
    """
    contract = {}
    for tool in defs.get("tools", []):
        params = {
            p["name"]: (p.get("type"), bool(p.get("required")))
            for p in tool.get("parameters", [])
        }
        contract[tool["name"]] = params
    return contract


def test_get_mcp_parameter_extracts_expected_contract(agent_server, backup_file):
    backup_file(TOOL_DEFS)
    result = run_smith("get_mcp_parameter", timeout=180, env=_mcp_env())
    assert result.returncode == 0, (
        f"get_mcp_parameter failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-1500:]}\n"
        f"--- stderr ---\n{result.stderr[-1000:]}"
    )

    # The file was written and is well-formed.
    assert TOOL_DEFS.exists(), "tool_definitions.json was not written"
    produced_doc = load_json(TOOL_DEFS)
    assert "tools" in produced_doc and produced_doc["tools"], "no tools extracted"

    # The extracted contract matches the hardcoded expectation exactly.
    produced = _tool_contract(produced_doc)
    assert produced == EXPECTED_CONTRACT, (
        "extracted tool contract differs from the expected server contract.\n"
        f"expected={EXPECTED_CONTRACT}\nproduced={produced}"
    )


# ---------------------------------------------------------------------------
# Session-config (`use_ir` / `selected_tools`) filtering.
#
# ---------------------------------------------------------------------------


def test_selected_tools_filters_out_unselected(agent_server, backup_file):
    # use_ir with a selection that excludes the server's only tool -> the written
    # doc must be empty and the flag must report dropping it.
    backup_file(TOOL_DEFS)
    cfg = _write_session_config(
        backup_file, use_ir=True, selected_tools=["some_other_tool"]
    )

    result = run_smith("get_mcp_parameter", timeout=180, env=_mcp_env(cfg))
    assert result.returncode == 0, result.stdout[-1500:] + result.stderr[-1000:]

    assert _tool_contract(load_json(TOOL_DEFS)) == {}, "unselected tool was not dropped"
    assert "keeping 0 selected tool(s)" in result.stdout
    assert "dropped 1" in result.stdout


def test_selected_tools_keeps_selected(agent_server, backup_file):
    # use_ir with the server's actual tool selected -> that tool is kept, with
    # its full parameter contract intact, and nothing is dropped.
    backup_file(TOOL_DEFS)
    cfg = _write_session_config(backup_file, use_ir=True, selected_tools=["get_events"])

    result = run_smith("get_mcp_parameter", timeout=180, env=_mcp_env(cfg))
    assert result.returncode == 0, result.stdout[-1500:] + result.stderr[-1000:]

    assert _tool_contract(load_json(TOOL_DEFS)) == EXPECTED_CONTRACT
    assert "keeping 1 selected tool(s)" in result.stdout
    assert "dropped 0" in result.stdout


def test_use_ir_false_applies_no_filtering(agent_server, backup_file):
    # A config that exists but has use_ir=false must NOT filter, even though it
    # names a selection — _selected_tools() returns None unless use_ir is true.
    backup_file(TOOL_DEFS)
    cfg = _write_session_config(
        backup_file, use_ir=False, selected_tools=["some_other_tool"]
    )

    result = run_smith("get_mcp_parameter", timeout=180, env=_mcp_env(cfg))
    assert result.returncode == 0, result.stdout[-1500:] + result.stderr[-1000:]

    assert _tool_contract(load_json(TOOL_DEFS)) == EXPECTED_CONTRACT
    assert "Session config:" not in result.stdout, "filtering ran despite use_ir=false"
