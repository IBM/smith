# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""
Translate an OPA (Rego) policy into a CPEX-compatible input shape.

CPEX expects a flatter input than the policies Smith generates:
  - the `extensions` layer is dropped, but `subject` is kept under the input root:
        input.extensions.subject        -> input.subject
        input.extensions.subject.role   -> input.subject.role
  - every other field under `extensions` collapses one level:
        input.extensions.agent          -> input.agent
  - tool arguments already live under `args` (Smith's native input shape uses
    `input.args`), so no arguments->args rewrite is needed here.

Both direct references (e.g. `subject := input.extensions.subject`) and the
indirect `object.get(...)` forms are handled:
        object.get(input, "extensions", {})              -> input
        object.get(object.get(input,"extensions",{}),"subject",{}) -> input.subject

CPEX also drops several OPA-envelope constructs that do not apply:
  - Package: `package mcp.policies` -> `package authz`.
  - Envelope validation: the `# === Envelope Validation ===` header, the whole
    `valid_envelope if { ... }` rule, and every `valid_envelope` / `not
    valid_envelope` reference in other rule bodies.
  - Tool-name guards: standalone `input.name == "..."` / `input.name != "..."`
    / `input.name in {...}` condition lines.
  - Allowed argument keys: the `# === Tool Argument Keys ===` /
    `# === Allowed Argument Keys ===` header, the whole `allowed_arg_keys := {
    ... }` block, any `known_tools` comprehension that references
    `allowed_arg_keys`, and any whole rule whose body references
    `allowed_arg_keys` (e.g. the `deny["unknown argument key for tool"]` rule),
    since that symbol no longer exists after translation. Such a rule is dropped
    head-through-`}` along with its immediately preceding comment header.
A rule body left with no conditions after these removals gets a `true`
inserted so the result stays valid rego.

The transform is a line-preserving text rewrite: only the target field paths
change; package name, rule names, and everything else are kept verbatim.

Usage:
    python src/smith/policy_generation/translate_cpex.py \
        --policy assets/policy.rego --dest assets/policy_cpex.rego
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

from smith.policy_generation.validate_policy import (
    validate_policy,
    run_opa_fmt_write,
)

# Order matters. The `subject` path is special (only `extensions` is dropped;
# `subject` is kept, so `input.extensions.subject` -> `input.subject`), so its
# rules must run BEFORE the generic `extensions.<tail>` collapse. Within each
# group the indirect `object.get` forms run before the direct dotted forms.
# Tool arguments are already under `input.args` natively, so there is no
# arguments->args transform here.
_TRANSFORMS = [
    # --- package rename: mcp.policies -> authz ---
    (
        "package mcp.policies -> package authz",
        re.compile(r"^package\s+mcp\.policies\b", re.MULTILINE),
        "package authz",
    ),
    # --- subject: drop the `extensions` layer but keep `subject` ---
    # 1a. Indirect subject via nested object.get:
    #     object.get(object.get(input,"extensions",{}),"subject",{}) -> input.subject
    (
        "indirect extensions.subject (object.get) -> input.subject",
        re.compile(
            r'object\.get\(\s*object\.get\(\s*input\s*,\s*"extensions"\s*,\s*[^)]*\)'
            r'\s*,\s*"subject"\s*,\s*[^)]*\)'
        ),
        "input.subject",
    ),
    # 1b. Direct dotted subject with a member tail:
    #     input.extensions.subject.<tail> -> input.subject.<tail>
    (
        "direct input.extensions.subject. prefix -> input.subject.",
        re.compile(r"\binput\.extensions\.subject\."),
        "input.subject.",
    ),
    # 1c. Direct dotted subject as a leaf: input.extensions.subject -> input.subject
    (
        "direct input.extensions.subject leaf -> input.subject",
        re.compile(r"\binput\.extensions\.subject\b"),
        "input.subject",
    ),
    # --- other extensions fields: collapse the extensions layer one level ---
    # 2a. Indirect extensions via object.get:
    #     object.get(input, "extensions", <default>) -> input
    #     Handles nested forms like object.get(object.get(input, "extensions",
    #     {}), "agent", {}) by removing the inner extensions accessor.
    (
        "indirect extensions (object.get) collapsed",
        re.compile(r'object\.get\(\s*input\s*,\s*"extensions"\s*,\s*[^)]*\)'),
        "input",
    ),
    # 2b. Direct dotted extensions: input.extensions.<tail> -> input.<tail>
    (
        "direct input.extensions. prefix collapsed",
        re.compile(r"\binput\.extensions\."),
        "input.",
    ),
    # 2c. Defensive: a trailing `input.extensions` with no member access. None
    #     exist today, but collapse it to `input` for completeness.
    (
        "trailing input.extensions collapsed",
        re.compile(r"\binput\.extensions\b"),
        "input",
    ),
    # Tool arguments already live under `input.args` in Smith's native input
    # shape, so no arguments->args transform is needed here.
]


# --- Line/block removal patterns (CPEX drops these entirely) ---
# The envelope-validation section header comment.
_ENVELOPE_HEADER = re.compile(r"^\s*#\s*=+\s*Envelope Validation\s*=+\s*$")
# Start of the `valid_envelope if {` rule block (the closing `}` ends it).
_ENVELOPE_RULE_START = re.compile(r"^\s*valid_envelope\s+if\s*\{\s*$")
# A standalone reference to valid_envelope used as a rule condition
# (optionally negated). These sit on their own line inside other rule bodies.
_ENVELOPE_REF = re.compile(r"^\s*(?:not\s+)?valid_envelope\s*$")
# A tool-name guard line: input.name compared to a literal, or membership in a
# set. Only simple standalone guard conditions are removed.
_TOOL_NAME_GUARD = re.compile(
    r'^\s*input\.name\s*(?:==|!=)\s*"[^"]*"\s*$'
    r"|^\s*input\.name\s+in\s+\{[^}]*\}\s*$"
)
# The argument-keys section header comment. Generated policies title it either
# `# === Tool Argument Keys ===` or `# === Allowed Argument Keys ===`.
_ARG_KEYS_HEADER = re.compile(r"^\s*#\s*=+\s*(?:Tool|Allowed) Argument Keys\s*=+\s*$")
# Start of the `allowed_arg_keys := ...` assignment.
_ARG_KEYS_START = re.compile(r"^\s*allowed_arg_keys\s*:=\s*\{")
# `known_tools := {t | allowed_arg_keys[t]}` — derived from allowed_arg_keys.
_KNOWN_TOOLS_FROM_ARG_KEYS = re.compile(
    r"^\s*known_tools\s*:=\s*\{.*allowed_arg_keys.*\}\s*$"
)
# The opening line of any rule body we may need to repair if it becomes empty:
# `<head> if {` (or `... contains ... if {`, `deny[...] if {`, etc.).
_RULE_BODY_OPEN = re.compile(r"\bif\s*\{\s*$")
# A reference to the `allowed_arg_keys` symbol anywhere in a line (word-boundary
# so it does not match a longer identifier that merely contains the substring).
_ARG_KEYS_REF = re.compile(r"\ballowed_arg_keys\b")


def _strip_and_repair(text: str, counts: dict) -> str:
    """Remove envelope validation, tool-name guards, and allowed_arg_keys, then
    repair empty bodies.

    Operates line-by-line: drops the envelope header/rule/references,
    standalone `input.name` guard lines, and the allowed_arg_keys block,
    then inserts `true` into any rule body left with no conditions so the
    output stays valid rego.
    """
    lines = text.split("\n")
    kept = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _ENVELOPE_HEADER.match(line):
            counts["envelope header removed"] += 1
            i += 1
            continue
        if _ENVELOPE_RULE_START.match(line):
            # Skip the whole `valid_envelope if { ... }` block through its `}`.
            counts["valid_envelope rule removed"] += 1
            i += 1
            while i < len(lines) and lines[i].strip() != "}":
                i += 1
            i += 1  # skip the closing brace too
            continue
        if _ENVELOPE_REF.match(line):
            counts["valid_envelope reference removed"] += 1
            i += 1
            continue
        if _TOOL_NAME_GUARD.match(line):
            counts["tool-name guard removed"] += 1
            i += 1
            continue
        if _ARG_KEYS_HEADER.match(line):
            counts["allowed_arg_keys header removed"] += 1
            i += 1
            continue
        if _ARG_KEYS_START.match(line):
            # Use brace counting to handle nested braces (e.g. sets inside the map).
            counts["allowed_arg_keys block removed"] += 1
            depth = line.count("{") - line.count("}")
            i += 1
            while i < len(lines) and depth > 0:
                depth += lines[i].count("{") - lines[i].count("}")
                i += 1
            continue
        if _KNOWN_TOOLS_FROM_ARG_KEYS.match(line):
            counts["known_tools (from allowed_arg_keys) removed"] += 1
            i += 1
            continue
        # Whole-rule removal: a rule whose body references `allowed_arg_keys`
        # depends on the symbol we just deleted, so drop the entire block
        # (head line through its closing `}`). Rules that only reference
        # `input.name` are left to the guard-line stripper above.
        if _RULE_BODY_OPEN.search(line):
            end = i + 1
            while end < len(lines) and lines[end].strip() != "}":
                end += 1
            block = lines[i : end + 1] if end < len(lines) else lines[i:]
            if any(_ARG_KEYS_REF.search(bl) for bl in block):
                # Also drop an immediately preceding `# ===`-style comment header
                # and any blank line that titled this rule, so no orphan remains.
                while kept and kept[-1].strip() == "":
                    kept.pop()
                if kept and kept[-1].lstrip().startswith("#"):
                    kept.pop()
                counts["rule referencing allowed_arg_keys removed"] += 1
                i = end + 1
                continue
        kept.append(line)
        i += 1

    # Repair: any rule body opened with `if {` and immediately closed by `}`
    # (only blank lines between) has lost all its conditions; insert `true`.
    repaired = []
    for idx, line in enumerate(kept):
        repaired.append(line)
        if _RULE_BODY_OPEN.search(line):
            j = idx + 1
            while j < len(kept) and kept[j].strip() == "":
                j += 1
            if j < len(kept) and kept[j].strip() == "}":
                indent = re.match(r"\s*", line).group(0) + "    "
                repaired.append(f"{indent}true")
                counts["empty body repaired with true"] += 1
    return "\n".join(repaired)


def translate_text(policy_text: str) -> tuple:
    """Apply the CPEX transforms to policy text.

    Returns (translated_text, counts) where counts maps each transform label to
    the number of substitutions/removals made.
    """
    counts = {}
    text = policy_text
    for label, pattern, replacement in _TRANSFORMS:
        text, n = pattern.subn(replacement, text)
        counts[label] = n

    for label in (
        "envelope header removed",
        "valid_envelope rule removed",
        "valid_envelope reference removed",
        "tool-name guard removed",
        "allowed_arg_keys header removed",
        "allowed_arg_keys block removed",
        "known_tools (from allowed_arg_keys) removed",
        "rule referencing allowed_arg_keys removed",
        "empty body repaired with true",
    ):
        counts[label] = 0
    text = _strip_and_repair(text, counts)
    return text, counts


def translate_policy_to_cpex(src_path: str, dest_path: str) -> bool:
    """Read src_path, write a CPEX-compatible copy to dest_path.

    Validates the output with `opa` when it is available (a missing `opa`
    binary is a non-fatal warning). Returns True on success.
    """
    src = Path(src_path)
    if not src.exists():
        print(f"ERROR: Policy file not found: {src_path}")
        return False

    original = src.read_text(encoding="utf-8")
    translated, counts = translate_text(original)

    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(translated, encoding="utf-8")

    print(f"CPEX translation: {src_path} -> {dest_path}")
    print("=" * 60)
    for label, n in counts.items():
        print(f"  {n:>3} x {label}")
    print("=" * 60)

    if shutil.which("opa") is None:
        print(
            "WARNING: 'opa' binary not found in PATH; skipping formatting and "
            "validation of the translated policy. Install OPA to validate: "
            "https://www.openpolicyagent.org/docs/latest/#1-download-opa"
        )
        return True

    # Tidy the removed-block whitespace (e.g. the gap left by the envelope rule)
    # before validating, so the delivered file is opa-formatted.
    fmt_ok, fmt_msg = run_opa_fmt_write(dest_path)
    print(f"[{'PASS' if fmt_ok else 'FAIL'}] opa fmt -w: {fmt_msg}")

    if not validate_policy(dest_path):
        print(
            "WARNING: the translated policy did not pass opa validation. "
            "Review the output above."
        )
        return False
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Translate an OPA policy to a CPEX-compatible input shape"
    )
    parser.add_argument("--policy", required=True, help="Path to the source .rego file")
    parser.add_argument(
        "--dest",
        help="Destination .rego path (default: <policy>_cpex.rego)",
    )
    args = parser.parse_args()

    src = args.policy
    dest = args.dest or (re.sub(r"\.rego$", "_cpex.rego", src) or (src + "_cpex"))
    if dest == src:
        dest = src + "_cpex"

    sys.exit(0 if translate_policy_to_cpex(src, dest) else 1)


if __name__ == "__main__":
    main()
