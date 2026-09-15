# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag test_case_translation``.

Translation asks the **real target agent** which tool each case's prompt actually
resolves to, and writes ``input.name`` + ``input.args`` back into the case file::

    for each case in test_cases/{allow,disallow}/
        POST <agent>/extract_tool_call {question, user_profile}
        -> input.name, input.args written back
        -> or moved aside if the agent disagrees / names no tool

Driven through the **real CLI**. This file imports nothing from ``smith``, so every
assertion reads a case file the run rewrote.

STEPS COVERED (all from the single run)
--------------------------------------
STEP 1  the pre-pass          — an ``other`` case is quarantined with no request
STEP 2  ``/extract_tool_call`` — the real agent resolves a crafted prompt
STEP 3  routing               — agreeing cases stay, disagreeing ones move aside
STEP 4  re-runnability        — an already-translated case is left untouched
STEP 5  ``miscalled_cases.json``

COST: THE FLAG IS RUN ONCE
--------------------------
Every untranslated case costs one agent call, and each of those is a model call
inside the agent. So the flag runs **exactly once** in a module-scoped fixture over
a **crafted four-case tree** — one per routing branch — rather than over whatever
``test_generation`` last produced. That keeps the bill at two calls (the ``other``
and already-translated cases cost nothing by design) and makes each branch
deterministic.

ASSERTING CORRECTNESS
---------------------
The agent's tool choice is a model decision, so it is asserted only where the
crafted prompt has one defensible answer:

* A prompt that names the task directly ("Search for academic conferences about
  Artificial intelligence") must resolve to ``get_events`` — the example agent
  exposes exactly one tool, so there is no competing alternative to pick.
* Which *arguments* it extracts is left unasserted beyond being a dict: the model
  legitimately decides whether to fill ``limit``, and demanding a specific value
  would be asserting more confidence than the prompt warrants.
* The pre-pass, the skip guard and the report are pure code, so those are exact.

The case tree is backed up and restored, and the crafted cases are written into a
throwaway path so the example's own files are never touched.

Requires the example agent (``agent_server``) and its inference credentials
(``requires_agent_inference``) — a *different* consumer from Smith's ``OPENAI_*``.
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


#: A prompt that names the agent's one tool's job directly, so the resolution has
#: a single defensible answer rather than depending on the model's latitude.
CLEAR_PROMPT = "Search for academic conferences about Artificial intelligence."

#: The four crafted cases, one per routing branch.
RESOLVES = "test_case_resolves.json"  # -> translated in place
ALREADY_DONE = "test_case_done.json"  # -> skipped, no request
NO_TOOL = "test_case_other.json"  # -> quarantined, no request
UNRELATED = "test_case_unrelated.json"  # -> resolves to nothing / a mismatch


def _case(name="get_events", prompt=CLEAR_PROMPT, args=None):
    inner = {
        "kind": "tool_call",
        "action": "execute",
        "name": name,
        "extensions": {
            "subject": {"user_name": "Ann", "user_role": ["faculty"]},
            "agent": {"input": prompt},
        },
    }
    if args is not None:
        inner["args"] = args
    return {"input": inner}


@pytest.fixture(scope="module")
def completed_run(request):
    """Run ``test_case_translation`` ONCE over a crafted tree; yield the result."""
    import os
    import time

    from helpers import SmithEnv, which

    env = SmithEnv()
    missing = env.missing("INFERENCE_MODEL", "INFERENCE_BASE_URL", "INFERENCE_API_KEY")
    if missing:
        pytest.skip(f"agent inference not configured (missing {', '.join(missing)})")
    example = env.example
    if not (example / "agent.py").exists():
        pytest.skip("call-for-papers example not found")
    if not which("uvicorn"):
        pytest.skip("uvicorn not installed")

    cases = env.test_cases
    backup_dir = Path(tempfile.mkdtemp(prefix="smith_xlate_backup_"))
    saved = None
    if cases.exists():
        saved = backup_dir / "test_cases"
        shutil.copytree(cases, saved)

    # --- boot the agent on a free port ---------------------------------
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    agent_url = f"http://127.0.0.1:{port}"

    agent = subprocess.Popen(
        ["uvicorn", "agent:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(example),
        env=dict(os.environ),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        import urllib.error
        import urllib.request

        deadline = time.time() + 60
        healthy = False
        while time.time() < deadline:
            if agent.poll() is not None:
                out = agent.stdout.read() if agent.stdout else ""
                pytest.fail(f"the example agent exited during startup:\n{out[-1500:]}")
            try:
                with urllib.request.urlopen(f"{agent_url}/health", timeout=2) as resp:
                    healthy = resp.status == 200
            except urllib.error.HTTPError:
                healthy = True  # up, just not 200
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.5)
            if healthy:
                break
        if not healthy:
            # A present-but-broken agent is a real problem, not a skip.
            pytest.fail(f"the example agent did not become healthy on {agent_url}")

        # --- stage the crafted tree ------------------------------------
        if cases.exists():
            shutil.rmtree(cases)
        for label in ("allow", "disallow"):
            (cases / label).mkdir(parents=True, exist_ok=True)

        (cases / "allow" / RESOLVES).write_text(json.dumps(_case(), indent=4))
        (cases / "allow" / ALREADY_DONE).write_text(
            json.dumps(_case(args={"topic": "Artificial intelligence"}), indent=4)
        )
        (cases / "allow" / NO_TOOL).write_text(
            json.dumps(_case(name="other", prompt="What is the weather?"), indent=4)
        )
        (cases / "disallow" / UNRELATED).write_text(
            json.dumps(
                _case(prompt="Tell me a joke about penguins, nothing else."), indent=4
            )
        )

        result = subprocess.run(
            [sys.executable, "-m", "smith.cli", "--flag", "test_case_translation"],
            cwd=str(env.base),
            env=env.override(AGENT_URL=agent_url),
            capture_output=True,
            text=True,
            timeout=1200,
        )
        yield {"result": result, "cases": cases, "agent_url": agent_url}
    finally:
        agent.terminate()
        try:
            agent.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            agent.kill()
            agent.communicate()
        if cases.exists():
            shutil.rmtree(cases, ignore_errors=True)
        if saved is not None:
            shutil.copytree(saved, cases)
        shutil.rmtree(backup_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def run_ok(completed_run):
    """The run must have succeeded before any artifact assertion is meaningful."""
    result = completed_run["result"]
    assert result.returncode == 0, (
        f"test_case_translation failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-2500:]}\n"
        f"--- stderr ---\n{result.stderr[-1200:]}"
    )
    return completed_run


@pytest.fixture(scope="module")
def tree(run_ok):
    """Every case file the run left, keyed by path relative to the tree root."""
    root = run_ok["cases"]
    return {
        str(p.relative_to(root)): p
        for p in root.rglob("*.json")
        if p.name != "miscalled_cases.json"
    }


# ===========================================================================
# STEP 1 — the pre-pass costs nothing
# ===========================================================================


def test_a_case_naming_no_tool_is_quarantined(tree):
    # Pure code, no model involved: `name == "other"` is moved before the request
    # loop, so it is asserted exactly.
    assert (
        f"wrong_cases/mcp_unrelated/allow/{NO_TOOL}" in tree
    ), f"the 'other' case was not quarantined; tree was {sorted(tree)}"


# ===========================================================================
# STEP 2 — the real agent resolves the prompt
# ===========================================================================


def test_the_clearly_worded_case_was_translated_in_place(tree):
    path = tree.get(f"allow/{RESOLVES}")
    assert (
        path is not None
    ), f"the clearly-worded case was moved aside; tree was {sorted(tree)}"

    case = json.loads(path.read_text())
    assert case["input"]["name"] == "get_events"


def test_the_translated_case_gained_an_args_block(tree):
    # `args` is the field the policy's argument rules read, and its presence is
    # also the idempotency marker for a re-run. Which arguments the model chose to
    # fill is its own call, so only the shape is asserted.
    case = json.loads(tree[f"allow/{RESOLVES}"].read_text())
    assert "args" in case["input"], "translation did not add an args block"
    assert isinstance(case["input"]["args"], dict)


def test_the_envelope_survived_the_rewrite(tree):
    # The file is rewritten wholesale, so the fields translation does NOT own must
    # come back unchanged — OPA reads all of them.
    inner = json.loads(tree[f"allow/{RESOLVES}"].read_text())["input"]
    assert inner["kind"] == "tool_call"
    assert inner["action"] == "execute"
    assert inner["extensions"]["agent"]["input"] == CLEAR_PROMPT
    assert inner["extensions"]["subject"]["user_role"] == ["faculty"]


# ===========================================================================
# STEP 4 — the skip guard
# ===========================================================================


def test_an_already_translated_case_was_left_exactly_as_written(tree):
    case = json.loads(tree[f"allow/{ALREADY_DONE}"].read_text())
    assert case["input"]["args"] == {
        "topic": "Artificial intelligence"
    }, "an already-translated case was re-resolved and overwritten"


# ===========================================================================
# STEP 5 — the report
# ===========================================================================


def test_the_report_is_written(run_ok):
    path = run_ok["cases"] / "miscalled_cases.json"
    assert path.exists(), f"no miscalled_cases.json at {path}"
    assert isinstance(json.loads(path.read_text()), list)


def test_every_reported_miscall_names_both_tools(run_ok):
    entries = json.loads((run_ok["cases"] / "miscalled_cases.json").read_text())
    for entry in entries:
        for field in (
            "file_path",
            "label",
            "assigned_tool",
            "actual_tool",
            "agent_input",
        ):
            assert field in entry, f"report entry missing {field}: {entry}"
        assert entry["label"] in {"allow", "disallow"}
        assert (
            entry["assigned_tool"] != entry["actual_tool"]
            or entry["actual_tool"].lower() == "other"
        ), ("a case was reported as miscalled though the tools agree: " f"{entry}")


def test_every_reported_miscall_was_actually_moved_aside(run_ok, tree):
    # STEP 3 -> STEP 5: the report and the tree must agree. A case reported as
    # miscalled but still sitting in its bucket would be scored anyway.
    entries = json.loads((run_ok["cases"] / "miscalled_cases.json").read_text())
    for entry in entries:
        name = Path(entry["file_path"]).name
        label = entry["label"]
        assert f"wrong_cases/misclassified/{label}/{name}" in tree, (
            f"{name} was reported as miscalled but is not in misclassified/: "
            f"{sorted(tree)}"
        )


def test_the_flag_reports_its_totals(run_ok):
    # The summary is how a user sees how much was translated versus quarantined.
    stdout = run_ok["result"].stdout
    assert "Processing" in stdout
    assert "Done. Processed:" in stdout
    assert "Saved miscalled cases to:" in stdout
