# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the functions behind ``smith --flag generate_promptfoo_config``.

The flag turns Smith's guidance + system variables into a promptfoo redteam
config. It has **two distinct paths**, chosen by whether the output already
exists::

    no config yet   template + LLM(FULL_SYSTEM_PROMPT)     -> purpose, vars,
                                                              contexts, policy text
    config exists   existing + LLM(CONTEXT_ONLY_SYSTEM_PROMPT)
                                                           -> contexts + policy
                                                              text only, rest kept

Both paths then append a tool-parameter block to ``testGenerationInstructions``.

SCOPE: WHY THIS FLAG NEEDS A UNIT LANE
--------------------------------------
Unlike a thin OPA wrapper, this module makes many decisions of its own, and
several are **unreachable through the CLI**:

* The **update path** needs a pre-existing config. An integration run starts from
  a clean output path, so it only ever exercises the create path.
* **Idempotency** of the tool-parameter block is only observable across *two*
  runs — the marker block must be replaced, not stacked. Seeing that live costs
  two LLM calls.
* The **validation rejections** need a malformed model reply, which cannot be
  requested from a real model.
* ``_strip_internal_context_vars`` guards against Smith-internal vars leaking
  into every generated test case — visible only with a crafted context.

So the LLM is faked and everything else runs for real.

FUNCTIONS UNDER TEST
--------------------
Listed — and laid out in this file — in the order the flag executes them.

STEP 1 · the model call and its validation
    ``_validate_llm_output``           — each rejected shape (create path)
    ``_validate_contexts``             — each rejected shape (both paths)
STEP 3 · shaping what the model returned
    ``_strip_internal_context_vars``   — internal vars never reach contexts[].vars
    ``_format_contexts``               — literal block style for purpose
STEP 4 · the tool-parameter block
    ``_build_tool_params_instructions``— required/optional split, empty inputs
    ``_strip_tool_params_instructions``— the idempotency mechanism
STEP 5 · the orchestrator, both paths
    ``generate_promptfoo_config``      — create from template; update in place
                                         preserving untouched keys; a rejected
                                         reply writes nothing; repeated runs stay
                                         idempotent
STEP 6 · the final check
    ``_validate_config``               — reports a valid config, and the pinned bug
                                         that its verdict is discarded

NOT COVERED HERE (integration lane — see ``test_generate_promptfoo_config_integration.py``)
    Whether a real model returns a usable purpose and contexts for real guidance,
    and the CLI wiring (MCP extraction, env-derived paths).

Deliberately absent: assertions on prompt text — a test pinning prompt wording
fails on every reword without catching a defect.

Env-free: the ``OpenAI`` boundary is patched, so no credentials and no network.
"""

from __future__ import annotations

import pytest
import yaml

from smith.test_generation import generate_promptfoo_config as gpc_mod
from smith.test_generation.generate_promptfoo_config import (
    _TOOL_PARAMS_MARKER,
    _build_tool_params_instructions,
    _format_contexts,
    _strip_internal_context_vars,
    _strip_tool_params_instructions,
    _validate_contexts,
    _validate_llm_output,
    generate_promptfoo_config,
)

from data_builders import (
    guidance,
    system_vars,
    tool_definitions,
    write_json,
    write_text,
)
from fakes import FakeOpenAI, fenced

pytestmark = pytest.mark.unit


#: The minimum template the create path needs: the skeleton it must preserve plus
#: the redteam keys it fills in.
TEMPLATE = """\
description: agent example
targets:
- id: http
  label: agent_name
  config:
    url: http://127.0.0.1:9000/chat
prompts:
- '{{prompt}}'
redteam:
  purpose: ''
  testGenerationInstructions: |
    Original instructions.
  vars: ''
  contexts: []
  plugins:
  - id: policy
    config:
      policy:
        text: ''
  - id: harmful:hate
"""


def ctx(id_="faculty_ai", purpose="A faculty member.", **vars_):
    """One context entry, as the model is asked to return it."""
    return {
        "id": id_,
        "purpose": purpose,
        "vars": dict(vars_) or {"user_role": "faculty"},
    }


def full_reply(*contexts, purpose="A research assistant agent."):
    """A well-formed reply for the create path."""
    return {"purpose": purpose, "contexts": list(contexts) or [ctx()]}


@pytest.fixture
def inputs(unit_env):
    """Guidance and system-vars files on disk, as the flag reads them."""
    return {
        "guidance": write_text(unit_env.root / "guidance.txt", guidance()),
        "system_vars": write_json(unit_env.root / "system_vars.json", system_vars()),
        "template": write_text(unit_env.root / "template.yaml", TEMPLATE),
        "output": unit_env.root / "references" / "promptfooconfig.yaml",
    }


def _run(inputs, monkeypatch, responses, tools=None):
    """Run the orchestrator with a faked model; return the parsed YAML output."""
    fake = FakeOpenAI(responses=responses)
    monkeypatch.setattr(gpc_mod, "OpenAI", fake.as_factory())
    generate_promptfoo_config(
        "test-key",
        "http://localhost/v1",
        "test-model",
        0.2,
        0.9,
        str(inputs["guidance"]),
        str(inputs["system_vars"]),
        "http://127.0.0.1:9000",
        str(inputs["output"]),
        str(inputs["template"]),
        tools,
    )
    if not inputs["output"].exists():
        return None, fake
    return yaml.safe_load(inputs["output"].read_text()), fake


# ===========================================================================
# STEP 1 · validating what the model returned
# ===========================================================================


@pytest.mark.parametrize(
    "contexts,why",
    [
        ([], "an empty list means the model produced no personas at all"),
        ({"id": "a"}, "a mapping is not a list of contexts"),
        ([{"id": "a", "purpose": "p"}], "a context without vars cannot be rendered"),
        ([{"id": "a", "vars": {}}], "a context without a purpose has no red-team goal"),
        ([{"id": "a", "purpose": "p", "vars": "not-a-dict"}], "vars must be a mapping"),
    ],
    ids=["empty", "not-a-list", "no-vars", "no-purpose", "vars-not-dict"],
)
def test_an_unusable_contexts_block_is_rejected(contexts, why):
    assert _validate_contexts(contexts) is False, why


def test_a_well_formed_contexts_block_is_accepted():
    assert _validate_contexts([ctx()]) is True


@pytest.mark.parametrize(
    "reply",
    [
        "a bare string",
        {"contexts": [ctx()]},
        {"purpose": 42, "contexts": [ctx()]},
        {"purpose": "p"},
        {"purpose": "p", "contexts": []},
    ],
    ids=[
        "not-a-dict",
        "no-purpose",
        "purpose-not-str",
        "no-contexts",
        "empty-contexts",
    ],
)
def test_an_unusable_full_reply_is_rejected(reply):
    # The create path fills purpose AND contexts from one reply, so either being
    # unusable makes the whole config unusable.
    assert _validate_llm_output(reply) is False


# ===========================================================================
# STEP 2 · shaping the contexts
# ===========================================================================


def test_internal_vars_never_reach_a_context():
    contexts = _strip_internal_context_vars(
        [ctx(user_role="faculty", action_list=["get_events"], action_description={})]
    )
    assert contexts[0]["vars"] == {"user_role": "faculty"}


def test_a_context_purpose_is_newline_terminated_for_block_style(unit_env):
    # promptfoo renders purpose as a literal block (|), which requires a trailing
    # newline; without it PyYAML emits a quoted scalar instead.
    formatted = _format_contexts([ctx(purpose="No trailing newline")])
    assert formatted[0]["purpose"] == "No trailing newline\n"


# ===========================================================================
# STEP 3 · the tool-parameter block and its idempotency
# ===========================================================================


def test_the_tool_block_separates_required_from_optional():
    # The whole point of the block is telling the generator which arguments it
    # MUST populate, so the split is the payload.
    text = _build_tool_params_instructions(
        tool_definitions(
            {
                "name": "get_events",
                "parameters": [
                    {"name": "topic", "required": True},
                    {"name": "keywords", "required": True},
                    {"name": "limit", "required": False},
                ],
            }
        )
    )
    assert "get_events: required(topic, keywords), optional(limit)" in text
    assert text.startswith(_TOOL_PARAMS_MARKER)


@pytest.mark.parametrize(
    "tools", [None, {}, {"tools": []}], ids=["none", "empty", "no-tools"]
)
def test_no_tools_appends_nothing(tools):
    # Without tool definitions there is nothing to say, and an empty marker block
    # would still be stripped-and-reappended on every run for no benefit.
    assert _build_tool_params_instructions(tools) == ""


def test_stripping_removes_a_previous_block_but_keeps_the_authored_text():
    """CORRECTNESS: the mechanism that keeps repeated runs idempotent."""
    block = _build_tool_params_instructions(tool_definitions())
    authored = "Original instructions."

    once = authored + "\n" + block
    stripped = _strip_tool_params_instructions(once)

    assert stripped == authored, "the human-authored prefix must survive"
    assert (stripped + "\n" + block).count(_TOOL_PARAMS_MARKER) == 1


def test_stripping_text_with_no_marker_is_a_no_op():
    # The first run has no marker yet; the authored text must pass through intact
    # (minus trailing blank lines, which YAML block style re-adds).
    assert (
        _strip_tool_params_instructions("Just authored text.\n")
        == "Just authored text."
    )


# ===========================================================================
# STEP 4 · generate_promptfoo_config — the create path
# ===========================================================================


def test_the_create_path_fills_the_template_and_keeps_its_skeleton(inputs, monkeypatch):
    config, fake = _run(inputs, monkeypatch, [full_reply(ctx())])

    # Filled from the model and from system_vars.
    assert config["redteam"]["purpose"].strip() == "A research assistant agent."
    assert config["redteam"]["contexts"][0]["id"] == "faculty_ai"
    assert '"user_role"' in config["redteam"]["vars"]
    # The guidance becomes the policy plugin's text — that is what promptfoo
    # red-teams against, so an empty one would test nothing.
    policy = next(p for p in config["redteam"]["plugins"] if p.get("id") == "policy")
    assert "faculty" in policy["config"]["policy"]["text"]
    # Skeleton preserved from the template rather than regenerated.
    assert config["targets"][0]["id"] == "http"
    assert config["prompts"] == ["{{prompt}}"]
    # Non-policy plugins are left alone.
    assert "harmful:hate" in [
        p.get("id") if isinstance(p, dict) else p for p in config["redteam"]["plugins"]
    ]
    assert len(fake.calls) == 1, "the create path is a single model call"


def test_a_fenced_reply_is_still_usable(inputs, monkeypatch):
    # Models fence JSON despite instructions not to; unstripped, the config would
    # be rejected as malformed and nothing written.
    config, _ = _run(inputs, monkeypatch, [fenced(full_reply())])
    assert config["redteam"]["purpose"].strip() == "A research assistant agent."


def test_a_rejected_reply_writes_no_config(inputs, monkeypatch, capsys):
    # Better to leave no file than a half-filled config: promptfoo would run
    # against an empty purpose and silently generate nothing useful.
    config, _ = _run(inputs, monkeypatch, [{"purpose": "p", "contexts": []}])
    assert config is None, "an invalid reply must not produce an output file"
    assert "invalid format" in capsys.readouterr().out


def test_internal_vars_are_stripped_end_to_end(inputs, monkeypatch):
    # The same leak as the unit-level test, but through the orchestrator, since
    # that is the path a real run takes.
    config, _ = _run(
        inputs,
        monkeypatch,
        [full_reply(ctx(user_role="faculty", action_list=["get_events"]))],
    )
    assert config["redteam"]["contexts"][0]["vars"] == {"user_role": "faculty"}


def test_the_tool_block_is_appended_to_the_authored_instructions(inputs, monkeypatch):
    config, _ = _run(inputs, monkeypatch, [full_reply()], tools=tool_definitions())
    tgi = config["redteam"]["testGenerationInstructions"]
    assert "Original instructions." in tgi, "the template's own text must survive"
    assert _TOOL_PARAMS_MARKER in tgi


# ===========================================================================
# STEP 4 · generate_promptfoo_config — the update path
#
# Reached only when the output already exists. An integration run starts clean,
# so this branch is unit-only.
# ===========================================================================


def test_the_update_path_replaces_contexts_but_preserves_everything_else(
    inputs, monkeypatch, capsys
):
    # First run creates the config.
    _run(
        inputs, monkeypatch, [full_reply(ctx("old_ctx"), purpose="Hand-tuned purpose.")]
    )

    # Second run: the model is asked for contexts ONLY, so it returns a bare list.
    config, fake = _run(inputs, monkeypatch, [[ctx("new_ctx")]])

    assert [c["id"] for c in config["redteam"]["contexts"]] == ["new_ctx"]
    assert (
        config["redteam"]["purpose"].strip() == "Hand-tuned purpose."
    ), "the update path must not regenerate purpose"
    assert "updating policy text only" in capsys.readouterr().out
    assert len(fake.calls) == 1


def test_the_update_path_refreshes_the_policy_text_from_guidance(inputs, monkeypatch):
    _run(inputs, monkeypatch, [full_reply()])
    # Guidance changes between runs — the config must follow it, since a stale
    # policy text would red-team against rules that no longer exist.
    inputs["guidance"].write_text("1. Only admins may call get_events.\n")

    config, _ = _run(inputs, monkeypatch, [[ctx()]])

    policy = next(p for p in config["redteam"]["plugins"] if p.get("id") == "policy")
    assert "admins" in policy["config"]["policy"]["text"]


def test_a_rejected_contexts_reply_leaves_the_existing_config_intact(
    inputs, monkeypatch, capsys
):
    # The destructive case: a bad reply on an update must not damage a config the
    # user already relies on.
    _run(inputs, monkeypatch, [full_reply(ctx("keep_me"))])
    before = inputs["output"].read_text()

    _run(inputs, monkeypatch, [[{"id": "broken"}]])

    assert (
        inputs["output"].read_text() == before
    ), "an invalid contexts reply must leave the existing config untouched"
    assert "invalid contexts format" in capsys.readouterr().out


def test_repeated_runs_do_not_stack_the_tool_block(inputs, monkeypatch):
    tools = tool_definitions()
    _run(inputs, monkeypatch, [full_reply()], tools=tools)
    config, _ = _run(inputs, monkeypatch, [[ctx()]], tools=tools)

    tgi = config["redteam"]["testGenerationInstructions"]
    assert (
        tgi.count(_TOOL_PARAMS_MARKER) == 1
    ), f"the tool block was appended twice:\n{tgi}"
    assert "Original instructions." in tgi


# ===========================================================================
# The final validation, and what it does *not* do
# ===========================================================================


def test_a_valid_config_is_reported_as_validated(inputs, monkeypatch, capsys):
    _run(inputs, monkeypatch, [full_reply()])
    assert "Validation passed" in capsys.readouterr().out
