# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag get_mcp_parameter``.

The flag asks a **real MCP server** what tools it exposes and writes the answer to
``<TARGET_AGENT_PATH>/smith/tool_definitions.json`` — the file every later stage
reads to learn which ``input.args.*`` a policy may reference::

    extract_tools(stdio)   launch `python server.py`, MCP handshake, list_tools
    tool_to_dict           each tool -> {name, description, parameters, input_schema}
    -> <TARGET_AGENT_PATH>/smith/tool_definitions.json

Driven through the **real CLI**. This file imports nothing from ``smith``, so every
assertion reads the file the run produced.

STEPS COVERED (all from the single run)
--------------------------------------
STEP 1  the real stdio transport — subprocess launch and MCP handshake
STEP 2  the schema conversion    — against the server's genuine tool signature
STEP 3  ``tool_definitions.json`` — written where later stages will look for it

COST
----
No LLM and no Docker: the only cost is launching the example MCP server as a
subprocess. The flag is still run **once**, in a module-scoped fixture.

WHAT ONLY THIS LANE CAN PROVE
-----------------------------
The unit lane converts hand-written schemas, so it *encodes* an assumption about
what a real MCP server sends. Only a live handshake confirms it:

* A ``FastMCP`` server derives its JSON Schema from **Python type hints**, so
  ``required`` comes from which parameters lack defaults. If that mapping differed
  from what ``tool_to_dict`` expects, every generated case would omit arguments the
  tool actually needs — and nothing downstream would notice.
* The three transports are real code paths in the MCP SDK, not Smith's; that stdio
  genuinely launches a server and completes ``initialize()`` + ``list_tools()`` is
  only observable here.

ASSERTING CORRECTNESS
---------------------
No model is involved — the answer is fixed by the server's source — so per the
guide the output is asserted exactly:

* The server declares ``get_events(keywords: str, topic: str, limit: int = 10)``,
  so ``keywords`` and ``topic`` must be **required** and ``limit`` **optional with
  default 10**. That is decided by Python's signature, not a judgement call.
* ``transport`` and ``source`` must record how the tools were obtained, since that
  provenance is all a reader of the file has.
* The parameter names must be exactly the tool's, because the policy's
  ``args.<name>`` rules are written against them.
  
Requires the MCP server's ``python`` (spawned over stdio).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


#: The one tool the call-for-papers example exposes.
EXPECTED_TOOL = "get_events"

#: From ``server.py``: ``get_events(keywords: str, topic: str, limit: int = 10)``.
#: FastMCP derives the schema from these hints, so the required/optional split is
#: fixed by the source rather than being a matter of interpretation.
REQUIRED_PARAMS = {"keywords", "topic"}
OPTIONAL_PARAMS = {"limit"}


@pytest.fixture(scope="module")
def completed_run():
    """Run ``get_mcp_parameter`` ONCE; yield the file it wrote."""
    import os

    from helpers import SmithEnv, which

    env = SmithEnv()
    if not which("python"):
        pytest.skip("python not on PATH (the MCP server is spawned over stdio)")

    workdir = Path(tempfile.mkdtemp(prefix="smith_mcp_", dir=str(env.base)))
    relative = os.path.relpath(workdir, str(env.base)) + "/"

    try:
        result = subprocess.run(
            [sys.executable, "-m", "smith.cli", "--flag", "get_mcp_parameter"],
            cwd=str(env.base),
            env=env.override(TARGET_AGENT_PATH=relative),
            capture_output=True,
            text=True,
            timeout=600,
        )
        yield {
            "result": result,
            "output": workdir / "smith" / "tool_definitions.json",
            "real_output": env.example / "smith" / "tool_definitions.json",
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@pytest.fixture(scope="module")
def run_ok(completed_run):
    """The run must have succeeded before any artifact assertion is meaningful."""
    result = completed_run["result"]
    assert result.returncode == 0, (
        f"get_mcp_parameter failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-2500:]}\n"
        f"--- stderr ---\n{result.stderr[-1200:]}"
    )
    return completed_run


@pytest.fixture(scope="module")
def definitions(run_ok):
    """The parsed ``tool_definitions.json`` — the artifact every test reads."""
    path = run_ok["output"]
    assert (
        path.exists()
    ), f"no tool_definitions.json at {path}\n{run_ok['result'].stdout[-2000:]}"
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def tool(definitions):
    """The single tool the example server exposes."""
    tools = definitions["tools"]
    assert tools, "the MCP server exposed no tools at all"
    match = next((t for t in tools if t["name"] == EXPECTED_TOOL), None)
    assert (
        match is not None
    ), f"{EXPECTED_TOOL} was not extracted; got {[t['name'] for t in tools]}"
    return match


# ===========================================================================
# STEP 1 — the real stdio transport, and its provenance
# ===========================================================================


def test_the_handshake_produced_at_least_one_tool(definitions, run_ok):
    # Proves the subprocess launched, initialize() completed and list_tools()
    # answered. A zero-tool result would still be valid JSON, so the count is the
    # only thing distinguishing a working handshake from a silent failure.
    assert definitions[
        "tools"
    ], f"no tools extracted:\n{run_ok['result'].stdout[-2000:]}"
    assert "Extracted 1 tools from MCP server" in run_ok["result"].stdout


def test_the_file_records_how_the_tools_were_obtained(definitions):
    # Provenance is all a reader of this file has: without it there is no way to
    # tell which server, or which transport, the definitions describe.
    assert definitions["transport"] == "stdio"
    assert (
        definitions["source"] == "python server.py"
    ), f"unexpected source provenance: {definitions.get('source')!r}"


# ===========================================================================
# STEP 2 — the conversion, against the server's genuine signature
# ===========================================================================


def test_the_tools_parameters_are_exactly_the_ones_it_declares(tool):
    names = {p["name"] for p in tool["parameters"]}
    assert names == REQUIRED_PARAMS | OPTIONAL_PARAMS


def test_the_required_split_matches_the_python_signature(tool):
    by_name = {p["name"]: p for p in tool["parameters"]}

    for name in REQUIRED_PARAMS:
        assert by_name[name]["required"] is True, f"{name} should be required"
    for name in OPTIONAL_PARAMS:
        assert by_name[name]["required"] is False, f"{name} should be optional"


def test_the_optional_parameters_default_is_carried_across(tool):
    # `limit: int = 10` in the signature. The default is what tells a case builder
    # what the tool does when the argument is omitted — and the policy caps `limit`,
    # so its baseline value is load-bearing.
    limit = next(p for p in tool["parameters"] if p["name"] == "limit")
    assert limit["default"] == 10
    assert (
        limit["type"] == "integer"
    ), f"expected the hinted type, got {limit['type']!r}"


def test_the_declared_types_survive(tool):
    # `args.limit > cap` in the policy is a numeric comparison, so a `limit` typed
    # as a string here would mean generated cases the rule silently cannot evaluate.
    by_name = {p["name"]: p["type"] for p in tool["parameters"]}
    assert by_name["keywords"] == "string"
    assert by_name["topic"] == "string"
    assert by_name["limit"] == "integer"


def test_the_docstring_reaches_the_tool_description(tool):
    # The tool description is interpolated into prompts by the bypass analyser and
    # the guidance classifier, so an empty one silently weakens every later model
    # call. FastMCP uses the docstring verbatim, Args block included.
    assert tool["description"].strip(), "the tool description is empty"
    assert (
        "keywords:" in tool["description"]
    ), "the docstring's Args block did not survive into the description"


def test_fastmcp_sends_no_per_parameter_descriptions(tool):
    assert not any(p.get("description") for p in tool["parameters"]), (
        "FastMCP now sends per-parameter descriptions; tool_to_dict already copies "
        "them, so this pin can be replaced with a positive assertion"
    )
    # The information is not lost, just relocated.
    assert "keywords:" in tool["description"]
    # And `title`, which FastMCP does send, is not carried into `parameters`.
    assert all("title" not in p for p in tool["parameters"])
    assert all("title" in prop for prop in tool["input_schema"]["properties"].values())


def test_the_raw_schema_is_preserved(tool):
    # `parameters` is a lossy convenience view; `input_schema` is the original, so
    # anything the flattening does not model stays recoverable.
    schema = tool["input_schema"]
    assert schema.get("properties"), "the raw JSON Schema was not preserved"
    assert set(schema["properties"]) == REQUIRED_PARAMS | OPTIONAL_PARAMS
    # And the two views must agree about what is required.
    assert set(schema.get("required", [])) == REQUIRED_PARAMS


# ===========================================================================
# STEP 3 — the file, and where it lands
# ===========================================================================


def test_the_flag_lists_each_tool_and_its_parameters(run_ok):
    # The stdout summary is how a user confirms the extraction without opening the
    # file, and it is what they check before pointing a policy at these arguments.
    stdout = run_ok["result"].stdout
    assert f"- {EXPECTED_TOOL} (" in stdout
    for name in REQUIRED_PARAMS | OPTIONAL_PARAMS:
        assert name in stdout, f"{name} was not reported on stdout"


def test_the_file_is_written_under_the_configured_agent(run_ok):
    # The path is TARGET_AGENT_PATH + "smith/tool_definitions.json", which is where
    # every later stage looks. Writing it anywhere else makes the run a no-op.
    assert run_ok["output"].parent.name == "smith"
    assert run_ok["output"].name == "tool_definitions.json"


def test_the_committed_definitions_were_not_overwritten(run_ok):
    real = run_ok["real_output"]
    if not real.exists():
        pytest.skip("the example agent has no committed tool_definitions.json")
    assert real != run_ok["output"], "the run targeted the committed file"
