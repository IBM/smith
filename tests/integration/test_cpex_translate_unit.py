# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the functions behind ``smith --flag cpex_translate``.

FUNCTIONS UNDER TEST
--------------------
Listed — and laid out in this file — in the order the flag executes them.

STEP 1 · ``smith.policy_generation.translate_cpex`` — the pure text transform
    ``translate_text``            — every transform: package rename, subject-path
                                    rewrite (direct + ``object.get`` forms),
                                    generic ``extensions`` collapse, and the
                                    ``counts`` report; plus the expressions it
                                    must leave alone (``input.args``)
    ``_strip_and_repair``         — the removals (envelope rule and references,
                                    tool-name guards, the ``allowed_arg_keys``
                                    block and any rule depending on it), the
                                    empty-body repair, and its pre-seeded
                                    ``counts`` contract

STEP 2 · the file wrapper, which writes and then optionally validates
    ``translate_policy_to_cpex``  — missing source; the destination written
                                    *before* OPA runs; the no-OPA early return;
                                    and the validation-failure path

NOT COVERED HERE (integration lane — see ``test_cpex_translate_integration.py``)
    Validating the translated policy with a real ``opa`` binary, and the real CLI
    destination behaviour.

Env-free: OPA availability and its results are patched, so these tests give the
same answer whether or not ``opa`` is installed.
"""

from __future__ import annotations

import pytest

from smith.policy_generation import translate_cpex
from smith.policy_generation.translate_cpex import (
    translate_text,
    translate_policy_to_cpex,
)

from data_builders import cpex_policy, write_text

pytestmark = pytest.mark.unit


# ===========================================================================
# STEP 1a · translate_text — the pure transform
# ===========================================================================


def test_package_is_renamed_to_authz():
    out, counts = translate_text("package mcp.policies\n\ndefault allow := false\n")
    assert "package authz" in out
    assert "package mcp.policies" not in out
    assert counts["package mcp.policies -> package authz"] == 1


def test_an_unrelated_package_name_is_left_alone():
    # Only `mcp.policies` is renamed; a policy in another package is not CPEX's
    # business and must pass through untouched.
    out, counts = translate_text("package something.else\n")
    assert "package something.else" in out
    assert counts["package mcp.policies -> package authz"] == 0


def test_subject_keeps_its_name_while_extensions_is_dropped():
    # The subject path is the special case: `extensions` goes, `subject` stays.
    out, _ = translate_text("subject := input.extensions.subject\n")
    assert "input.subject" in out
    assert "input.extensions" not in out


def test_subject_member_access_is_rewritten():
    out, counts = translate_text('x := input.extensions.subject.user_role[0]\n')
    assert "input.subject.user_role[0]" in out
    assert counts["direct input.extensions.subject. prefix -> input.subject."] == 1


def test_indirect_subject_via_object_get_is_rewritten():
    src = 'subject := object.get(object.get(input, "extensions", {}), "subject", {})\n'
    out, counts = translate_text(src)
    assert "input.subject" in out
    assert "object.get" not in out
    assert counts["indirect extensions.subject (object.get) -> input.subject"] == 1


def test_non_subject_extensions_fields_collapse_one_level():
    # Everything other than subject loses the `extensions` layer entirely.
    out, _ = translate_text('cmd := input.extensions.agent.input\n')
    assert "input.agent.input" in out
    assert "extensions" not in out


def test_indirect_non_subject_extensions_collapses():
    out, counts = translate_text('a := object.get(input, "extensions", {}).agent\n')
    assert "input.agent" in out
    assert counts["indirect extensions (object.get) collapsed"] == 1


def test_argument_expressions_are_untouched():
    # Tool arguments already live under input.args in Smith's native shape, so
    # there is deliberately no arguments->args transform. Guarding this prevents
    # a future "helpful" rewrite from breaking every argument check.
    src = 'allow if {\n\tinput.args.topic == "Artificial intelligence"\n}\n'
    out, _ = translate_text(src)
    assert 'input.args.topic == "Artificial intelligence"' in out


def test_rule_and_helper_names_are_preserved():
    # A line-preserving transform: only field paths change.
    src = (
        "package mcp.policies\n\n"
        "approved_topic if {\n"
        '\tinput.extensions.subject.role == "faculty"\n'
        "}\n"
    )
    out, _ = translate_text(src)
    assert "approved_topic if {" in out


def test_translate_text_returns_counts_for_every_transform():
    _, counts = translate_text(cpex_policy())
    # The report drives the CLI's summary output, so every label must be present
    # even when its count is zero.
    for label in (
        "package mcp.policies -> package authz",
        "direct input.extensions.subject leaf -> input.subject",
        "envelope header removed",
        "valid_envelope rule removed",
        "tool-name guard removed",
        "allowed_arg_keys block removed",
        "empty body repaired with true",
    ):
        assert label in counts, f"missing count label: {label}"
        assert isinstance(counts[label], int)


# ===========================================================================
# STEP 1b · translate_text — the removals and the empty-body repair
# ===========================================================================


def test_envelope_validation_rule_and_header_are_removed():
    src = (
        "package mcp.policies\n\n"
        "# === Envelope Validation ===\n"
        "valid_envelope if {\n"
        '\tinput.kind == "tool_call"\n'
        "}\n\n"
        "allow if {\n"
        "\tvalid_envelope\n"
        '\tinput.args.topic == "AI"\n'
        "}\n"
    )
    out, counts = translate_text(src)
    assert "valid_envelope" not in out, "every envelope reference must be gone"
    assert "Envelope Validation" not in out
    assert counts["valid_envelope rule removed"] == 1
    assert counts["valid_envelope reference removed"] == 1
    # The surviving condition is still there.
    assert 'input.args.topic == "AI"' in out


def test_tool_name_guard_lines_are_removed():
    src = (
        "allow if {\n"
        '\tinput.name == "get_events"\n'
        '\tinput.args.topic == "AI"\n'
        "}\n"
    )
    out, counts = translate_text(src)
    assert 'input.name == "get_events"' not in out
    assert counts["tool-name guard removed"] == 1
    assert 'input.args.topic == "AI"' in out


def test_allowed_arg_keys_block_is_removed_with_nested_braces():
    # Brace counting must handle the sets nested inside the map.
    src = (
        "package mcp.policies\n\n"
        "# === Tool Argument Keys ===\n"
        'allowed_arg_keys := {"get_events": {"keywords", "topic", "limit"}}\n\n'
        "default allow := false\n"
    )
    out, counts = translate_text(src)
    assert "allowed_arg_keys" not in out
    assert "Tool Argument Keys" not in out
    assert counts["allowed_arg_keys block removed"] == 1
    assert "default allow := false" in out


def test_a_rule_whose_body_needs_allowed_arg_keys_is_dropped_entirely():
    # The symbol no longer exists after translation, so a rule depending on it
    # cannot be kept — it is dropped head-through-`}`.
    src = (
        "package mcp.policies\n\n"
        'allowed_arg_keys := {"get_events": {"topic"}}\n\n'
        'deny["unknown argument key"] if {\n'
        "\tsome key\n"
        "\tnot allowed_arg_keys[input.name][key]\n"
        "}\n\n"
        "default allow := false\n"
    )
    out, _ = translate_text(src)
    assert "allowed_arg_keys" not in out
    assert "unknown argument key" not in out
    assert "default allow := false" in out


def test_a_body_emptied_by_removals_is_repaired_with_true():
    # Removing the only condition would leave `allow if { }`, which is invalid
    # rego; the transform inserts `true` so the output still parses.
    src = "allow if {\n" '\tinput.name == "get_events"\n' "}\n"
    out, counts = translate_text(src)
    assert counts["empty body repaired with true"] == 1
    assert "true" in out
    # Sanity: the rule head survived and the body is not empty.
    assert "allow if {" in out
    body = out.split("allow if {", 1)[1].split("}", 1)[0]
    assert body.strip(), "body must not be left empty"


def test_strip_and_repair_requires_preseeded_counts():
    # It does `counts[label] += 1`, so a bare dict raises. Callers go through
    # translate_text, which seeds every key first — this pins that contract so a
    # future direct caller gets a clear failure rather than a silent KeyError.
    with pytest.raises(KeyError):
        translate_cpex._strip_and_repair("valid_envelope\n", {})


# ===========================================================================
# STEP 2 · translate_policy_to_cpex — the file wrapper
# ===========================================================================


@pytest.fixture
def no_opa(monkeypatch):
    """Force the no-OPA path, so the result is identical on any machine."""
    monkeypatch.setattr(translate_cpex.shutil, "which", lambda _name: None)


def test_missing_source_returns_false_and_writes_nothing(unit_env, no_opa):
    dest = unit_env.root / "out.rego"
    assert translate_policy_to_cpex(str(unit_env.root / "nope.rego"), str(dest)) is False
    assert not dest.exists()


def test_translation_writes_the_destination_and_leaves_the_source_intact(
    unit_env, no_opa
):
    src = write_text(unit_env.root / "policy.rego", cpex_policy())
    dest = unit_env.root / "policy_cpex.rego"
    original = src.read_text()

    assert translate_policy_to_cpex(str(src), str(dest)) is True

    out = dest.read_text()
    assert "package authz" in out
    assert "input.subject" in out
    assert "input.extensions" not in out
    assert src.read_text() == original, "the source policy must not be modified"


def test_destination_parents_are_created(unit_env, no_opa):
    src = write_text(unit_env.root / "policy.rego", cpex_policy())
    dest = unit_env.root / "nested" / "deeper" / "out.rego"
    assert translate_policy_to_cpex(str(src), str(dest)) is True
    assert dest.exists()


def test_absent_opa_still_returns_true_having_written_the_file(unit_env, no_opa):
    # OPA is optional: without it the translation is delivered unvalidated
    # rather than failing, which is what makes this testable offline at all.
    src = write_text(unit_env.root / "policy.rego", cpex_policy())
    dest = unit_env.root / "out.rego"
    assert translate_policy_to_cpex(str(src), str(dest)) is True
    assert dest.exists()


def test_output_is_written_before_opa_runs(unit_env, monkeypatch):
    # Ordering matters: even when validation fails, the translated file is on
    # disk for inspection.
    monkeypatch.setattr(translate_cpex.shutil, "which", lambda _name: "/usr/bin/opa")
    monkeypatch.setattr(
        translate_cpex, "run_opa_fmt_write", lambda _p: (True, "formatted")
    )
    seen = {}

    def _validate(path):
        seen["existed_at_validation"] = __import__("pathlib").Path(path).exists()
        return False

    monkeypatch.setattr(translate_cpex, "validate_policy", _validate)

    src = write_text(unit_env.root / "policy.rego", cpex_policy())
    dest = unit_env.root / "out.rego"
    assert translate_policy_to_cpex(str(src), str(dest)) is False
    assert seen["existed_at_validation"] is True
    assert dest.exists()


def test_validation_failure_is_reported_as_false(unit_env, monkeypatch):
    monkeypatch.setattr(translate_cpex.shutil, "which", lambda _name: "/usr/bin/opa")
    monkeypatch.setattr(translate_cpex, "run_opa_fmt_write", lambda _p: (True, "ok"))
    monkeypatch.setattr(translate_cpex, "validate_policy", lambda _p: False)

    src = write_text(unit_env.root / "policy.rego", cpex_policy())
    assert (
        translate_policy_to_cpex(str(src), str(unit_env.root / "out.rego")) is False
    )


def test_successful_validation_is_reported_as_true(unit_env, monkeypatch):
    monkeypatch.setattr(translate_cpex.shutil, "which", lambda _name: "/usr/bin/opa")
    monkeypatch.setattr(translate_cpex, "run_opa_fmt_write", lambda _p: (True, "ok"))
    monkeypatch.setattr(translate_cpex, "validate_policy", lambda _p: True)

    src = write_text(unit_env.root / "policy.rego", cpex_policy())
    assert translate_policy_to_cpex(str(src), str(unit_env.root / "out.rego")) is True


def test_the_frozen_fixture_policy_translates_cleanly(unit_env, no_opa):
    # The real policy the integration lane scores, run through the transform: a
    # guard that the fixture and the translation stay compatible.
    dest = unit_env.root / "fixture_cpex.rego"
    assert translate_policy_to_cpex(str(unit_env.policy), str(dest)) is True
    out = dest.read_text()
    assert "package authz" in out
    assert "input.extensions" not in out
    assert "allowed_arg_keys" not in out
    assert "valid_envelope" not in out
