# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the functions behind ``smith --flag get_mcp_parameter``.

The flag asks an MCP server what tools it exposes and writes the answer to
``<TARGET_AGENT_PATH>/smith/tool_definitions.json`` — the file every later stage
reads to learn which ``input.args.*`` a policy may reference::

    extract_tools(transport)   sse | stdio | http  -> raw MCP tool objects
    tool_to_dict               each tool -> {name, description, parameters,
                                            input_schema}
    _selected_tools            drop tools the session config excludes
    -> tool_definitions.json

FUNCTIONS UNDER TEST
--------------------
Listed — and laid out in this file — in the order the flag executes them.

STEP 1 · ``smith.policy_generation.extract_tools``
    ``extract_tools``     — transport dispatch, the ``http`` short-circuit, the
                            ``source``/``transport`` provenance fields, and the
                            unknown-transport guard

STEP 2 · the schema conversion
    ``tool_to_dict``      — required vs optional, the ``type`` fallback, and each
                            optional field carried across, including the
                            ``enum`` -> ``candidates`` rename

STEP 3 · ``smith.cli``
    ``_selected_tools``   — how a session config restricts the tool set

NOT COVERED HERE (integration lane — see ``test_get_mcp_parameter_integration.py``)
    Real SSE / stdio / HTTP transports against a live MCP server, and that the
    written ``tool_definitions.json`` describes the tools that server truly exposes.

Env-free: no MCP server is contacted; the session/transport boundaries are patched.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from smith import cli as cli_mod
from smith.policy_generation import extract_tools as et_mod
from smith.policy_generation.extract_tools import extract_tools, tool_to_dict

from fakes import FakeTool

pytestmark = pytest.mark.unit


def _run(coro):
    """Drive one coroutine to completion."""
    return asyncio.run(coro)


# ===========================================================================
# STEP 1 · extract_tools — choosing a transport
# ===========================================================================


def test_the_sse_transport_records_the_url_it_read_from(monkeypatch):
    # `source` is provenance: it is written into tool_definitions.json so a reader
    # can tell which server the tools came from. For SSE that is the URL.
    async def fake_sse(url):
        assert url == "http://localhost:8000/sse"
        return [FakeTool("get_events")]

    monkeypatch.setattr(et_mod, "fetch_tools_sse", fake_sse)

    result = _run(extract_tools(transport="sse", url="http://localhost:8000/sse"))

    assert result["transport"] == "sse"
    assert result["source"] == "http://localhost:8000/sse"
    assert [t["name"] for t in result["tools"]] == ["get_events"]


def test_the_stdio_transport_records_the_command_it_launched(monkeypatch):
    # For stdio the provenance is the command line, reassembled from command+args —
    # the only record of *how* the server was started.
    async def fake_stdio(command, args, cwd=None):
        assert (command, args, cwd) == ("python", ["server.py"], "/tmp/agent")
        return [FakeTool("get_events")]

    monkeypatch.setattr(et_mod, "fetch_tools_stdio", fake_stdio)

    result = _run(
        extract_tools(
            transport="stdio",
            command="python",
            cmd_args=["server.py"],
            cwd="/tmp/agent",
        )
    )

    assert result["transport"] == "stdio"
    assert result["source"] == "python server.py"


def test_stdio_defaults_to_no_arguments(monkeypatch):
    # `cmd_args or []` — a None must become an empty list rather than crashing the
    # join that builds `source`.
    async def fake_stdio(command, args, cwd=None):
        assert args == []
        return []

    monkeypatch.setattr(et_mod, "fetch_tools_stdio", fake_stdio)

    result = _run(extract_tools(transport="stdio", command="server"))
    assert result["source"] == "server "


def test_the_http_transport_returns_the_agents_answer_verbatim(monkeypatch):
    payload = {"tools": [{"name": "get_employee", "parameters": []}], "custom": "kept"}
    monkeypatch.setattr(et_mod, "fetch_tools_http", lambda url: payload)

    result = _run(extract_tools(transport="http", url="http://localhost:9000/tools"))

    assert result == payload
    assert "transport" not in result, "the http path adds no provenance of its own"


def test_an_unknown_transport_raises_rather_than_returning_nothing(monkeypatch):
    # A typo in MCP_TRANSPORT must fail loudly. Returning an empty tool set would
    # let the whole pipeline run against no tools and look merely unproductive.
    with pytest.raises(ValueError, match="Unknown transport"):
        _run(extract_tools(transport="carrier-pigeon"))


# ===========================================================================
# STEP 2 · tool_to_dict — the JSON-Schema conversion
# ===========================================================================


def test_required_and_optional_parameters_are_distinguished():
    tool = FakeTool(
        "get_events",
        "Search conferences.",
        {
            "properties": {"topic": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["topic"],
        },
    )

    params = {p["name"]: p for p in tool_to_dict(tool)["parameters"]}

    assert params["topic"]["required"] is True
    assert params["limit"]["required"] is False


def test_a_parameter_without_a_declared_type_becomes_any():
    # MCP servers may expose a property with no `type`. "any" keeps the entry
    # present — dropping it would hide an argument the policy can still receive.
    tool = FakeTool("t", "", {"properties": {"mystery": {}}})

    param = tool_to_dict(tool)["parameters"][0]

    assert param == {"name": "mystery", "type": "any", "required": False}


@pytest.mark.parametrize(
    "schema_key,schema_value,out_key",
    [
        ("description", "The research topic", "description"),
        ("default", 10, "default"),
        ("enum", ["AI", "Security"], "candidates"),
        ("items", {"type": "string"}, "items"),
    ],
    ids=["description", "default", "enum-to-candidates", "items"],
)
def test_each_optional_schema_field_is_carried_across(
    schema_key, schema_value, out_key
):
    tool = FakeTool(
        "t", "", {"properties": {"p": {"type": "string", schema_key: schema_value}}}
    )

    param = tool_to_dict(tool)["parameters"][0]

    assert param[out_key] == schema_value


def test_absent_optional_fields_are_omitted_rather_than_nulled():
    # A `"default": null` would be indistinguishable from a real null default, so
    # the keys are left out entirely when the schema does not declare them.
    tool = FakeTool("t", "", {"properties": {"p": {"type": "string"}}})

    param = tool_to_dict(tool)["parameters"][0]

    assert set(param) == {"name", "type", "required"}


def test_the_raw_schema_is_preserved_alongside_the_flattened_parameters():
    # `parameters` is a lossy convenience view; `input_schema` is the original, so
    # anything the flattening does not model is still recoverable.
    schema = {
        "properties": {"p": {"type": "string", "minLength": 3}},
        "required": ["p"],
        "additionalProperties": False,
    }
    tool = FakeTool("t", "", schema)

    assert tool_to_dict(tool)["input_schema"] == schema


def test_a_tool_with_no_schema_yields_no_parameters():
    # A zero-argument tool is legitimate. It must still appear, with an empty
    # parameter list, so the policy knows the tool exists.
    result = tool_to_dict(FakeTool("ping", None, None))

    assert result == {
        "name": "ping",
        "description": "",
        "parameters": [],
        "input_schema": {},
    }


def test_a_missing_description_becomes_an_empty_string():
    # `description or ""` — the classifier and the bypass analyser both interpolate
    # this into a prompt, where a literal "None" would be misleading context.
    assert tool_to_dict(FakeTool("t", None, {}))["description"] == ""


def test_every_fetched_tool_is_converted(monkeypatch):
    # Steps 1 -> 2: the dispatch maps tool_to_dict over the whole list, so a
    # server exposing several tools must yield several entries.
    async def fake_sse(url):
        return [FakeTool("a"), FakeTool("b"), FakeTool("c")]

    monkeypatch.setattr(et_mod, "fetch_tools_sse", fake_sse)

    result = _run(extract_tools(transport="sse", url="http://x/sse"))

    assert [t["name"] for t in result["tools"]] == ["a", "b", "c"]
    # Converted, not passed through as MCP objects — the result must be JSON.
    json.dumps(result)


# ===========================================================================
# STEP 3 · _selected_tools — the session config's restriction
# ===========================================================================


def test_no_session_config_means_no_restriction(unit_env):
    # None is "keep everything", distinct from an empty set. The CLI keys on the
    # falsiness, so both read the same there — but None documents the intent.
    assert cli_mod._selected_tools(str(unit_env.root) + "/") is None


def test_ir_mode_off_means_no_restriction(unit_env):
    # The explorer writes use_ir=false when the user has not narrowed the run, so
    # a stale selected_tools list must not silently keep filtering.
    unit_env.write_json(
        "references/session_config.json",
        {"use_ir": False, "selected_tools": ["get_events"]},
    )
    assert cli_mod._selected_tools(str(unit_env.root) + "/") is None


def test_an_enabled_session_config_restricts_to_its_tools(unit_env):
    unit_env.write_json(
        "references/session_config.json",
        {"use_ir": True, "selected_tools": ["get_events", "other"]},
    )
    assert cli_mod._selected_tools(str(unit_env.root) + "/") == {"get_events", "other"}


def test_an_enabled_but_empty_selection_means_no_restriction(unit_env):
    # `set(tools_list) if tools_list else None` — an empty selection is treated as
    # "no restriction" rather than "drop every tool", which would leave the policy
    # with nothing to govern.
    unit_env.write_json(
        "references/session_config.json", {"use_ir": True, "selected_tools": []}
    )
    assert cli_mod._selected_tools(str(unit_env.root) + "/") is None
