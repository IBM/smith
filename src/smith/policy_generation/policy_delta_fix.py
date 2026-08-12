"""
Policy Delta Fix
================

Automated loop that measures policy pass rate, calls an LLM to diagnose
failing test cases, applies targeted fixes, and repeats until 100 % pass rate
or a stopping condition is hit.

Stopping conditions (in priority order):
  1. 100 % pass rate on both allow and deny cases  → SUCCESS
  2. --max_iter iterations reached (default 10)    → MAX ITERATIONS
  3. --stall_limit consecutive zero-delta or
     regression iterations (default 3)             → STALLED

Usage (via CLI):
  smith --flag policy_delta_fix \\
      --policy_path <path>/policy.rego \\
      --test_cases_dir <path>/test_cases \\
      --max_iter 10 \\
      --stall_limit 3
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import List, Optional, Tuple

import httpx
from openai import OpenAI

from smith.policy_generation.policy_delta_test import (
    load_test_cases,
    evaluate,
    _infer_query_url,
    _read_policy,
)


# ===========================================================================
#  Prompts
# ===========================================================================

_SYSTEM_PROMPT = """\
You are an OPA (Open Policy Agent) Rego policy expert.
You will be given a Rego policy, the OPA input envelope structure, and failing test cases.

CRITICAL: Your response must be ONLY a JSON object. No prose, no explanation, no markdown outside the JSON.
Start your response with {{ and end with }}. Nothing else.

JSON structure:
{{
  "fixes": [
    {{
      "diagnosis": "one sentence explaining the root cause",
      "old_text": "exact verbatim text from the policy to replace",
      "new_text": "replacement text"
    }}
  ]
}}

## OPA input envelope

Each test case is evaluated as `input` in the policy. The envelope structure is:

{test_case_template}

Key mappings:
- `input.name`                    — the MCP tool being called
- `input.arguments.*`             — tool parameters
- `input.extensions.subject.*`    — system/session variables (role, user_id, etc.)

Use this structure to trace exactly which field a deny rule is reading
and why it fires (or fails to fire) for a given test case input.

## Rules
- old_text MUST be copied verbatim from the policy — it is used for exact string replacement.
- Fix only the rules implicated by the failing cases.
- Do not refactor, rename, or restructure unrelated rules.
- Multiple failing cases may share the same root cause — one fix entry is enough.
- If a false allow case has no matching deny rule, add one (use a nearby rule as the anchor).
- FALSE DENY = expected ALLOW but policy denied — a deny rule is firing incorrectly.
- FALSE ALLOW = expected DENY but policy allowed — a deny rule is missing or too narrow.
"""

_USER_TEMPLATE = """\
## Policy

```rego
{policy_text}
```

## Failing Test Cases

### False Denies (expected ALLOW, policy returned DENY)
{false_denies}

### False Allows (expected DENY, policy returned ALLOW)
{false_allows}

Diagnose the root cause and return the JSON fixes.
"""


# ===========================================================================
#  LLM call
# ===========================================================================

def _format_cases(cases: List[Tuple[str, dict]]) -> str:
    if not cases:
        return "(none)"
    parts = []
    for path, input_doc in cases:
        parts.append(
            f"File: {os.path.basename(path)}\n```json\n{json.dumps(input_doc, indent=2)}\n```"
        )
    return "\n\n".join(parts)


def _call_llm(
    policy_text: str,
    false_denies: List[Tuple[str, dict]],
    false_allows: List[Tuple[str, dict]],
    test_case_template: str,
    api_key: str,
    openai_base_url: str,
    model: str,
    temp: float,
    top_p: float,
) -> List[dict]:
    http_client = httpx.Client(verify=False, timeout=300.0)
    client = OpenAI(api_key=api_key, base_url=openai_base_url, http_client=http_client)

    system_prompt = _SYSTEM_PROMPT.format(test_case_template=test_case_template)

    user_prompt = _USER_TEMPLATE.format(
        policy_text=policy_text,
        false_denies=_format_cases(false_denies),
        false_allows=_format_cases(false_allows),
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temp,
        top_p=top_p,
    )

    llm_output = response.choices[0].message.content.strip()

    # Try markdown json fence first
    match = re.search(r"```json\s*(.*?)```", llm_output, re.DOTALL)
    if match:
        llm_output = match.group(1).strip()

    # Fallback: extract outermost {...} from anywhere in the response
    if not llm_output.startswith("{"):
        match = re.search(r"\{.*\}", llm_output, re.DOTALL)
        if match:
            llm_output = match.group(0)

    try:
        return json.loads(llm_output).get("fixes", [])
    except (json.JSONDecodeError, AttributeError):
        print("  warning: failed to parse LLM response as JSON")
        return []


# ===========================================================================
#  Fix application and OPA validation
# ===========================================================================

def _apply_fixes(policy_text: str, fixes: List[dict]) -> Tuple[str, int]:
    n_applied = 0
    for fix in fixes:
        old = fix.get("old_text", "")
        new = fix.get("new_text", "")
        if not old:
            continue
        if old in policy_text:
            policy_text = policy_text.replace(old, new, 1)
            n_applied += 1
        else:
            preview = old[:60].replace("\n", "\\n")
            print(f"  warning: fix text not found in policy — skipped: {preview!r}")
    return policy_text, n_applied


def _validate_opa(policy_path: str) -> Tuple[bool, str]:
    if shutil.which("opa") is None:
        return False, "opa binary not found in PATH"
    r = subprocess.run(["opa", "fmt", "-w", policy_path], capture_output=True, text=True)
    if r.returncode != 0:
        return False, f"opa fmt: {r.stderr.strip()}"
    r = subprocess.run(["opa", "check", policy_path], capture_output=True, text=True)
    if r.returncode != 0:
        return False, f"opa check: {r.stderr.strip()}"
    return True, ""


def _push_policy_to_opa(opa_url: str, policy_text: str) -> Tuple[bool, str]:
    """PUT the policy content to the OPA server so evaluations use the latest version."""
    import urllib.request, urllib.error
    try:
        # Get current policy ID
        with urllib.request.urlopen(f"{opa_url}/v1/policies", timeout=10) as r:
            policies = json.loads(r.read()).get("result", [])
        if not policies:
            return False, "no policies loaded on OPA server"
        policy_id = policies[0]["id"]

        # PUT updated content
        body = policy_text.encode("utf-8")
        req = urllib.request.Request(
            f"{opa_url}/v1/policies/{policy_id}",
            data=body,
            headers={"Content-Type": "text/plain"},
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
        return True, ""
    except urllib.error.HTTPError as e:
        return False, f"OPA PUT failed ({e.code}): {e.read().decode()[:200]}"
    except Exception as e:
        return False, str(e)


# ===========================================================================
#  Main loop
# ===========================================================================

def run(
    policy_path: str,
    test_cases_dir: str,
    opa_url: str,
    previous_path: Optional[str],
    max_iter: int,
    stall_limit: int,
    api_key: str,
    openai_base_url: str,
    model: str,
    temp: float,
    top_p: float,
    verbose: bool,
) -> None:
    opa_url = opa_url.rstrip("/")

    print(f"Connecting to OPA at {opa_url} ...")
    query_url = _infer_query_url(opa_url)
    print(f"  query url  : {query_url}")

    # Load the canonical OPA input envelope template
    template_path = os.path.join(
        os.getenv("BASE_URL", ""), os.getenv("TEST_CASE_TEMPLATE", "references/test_case_template.json")
    )
    try:
        with open(template_path) as fh:
            test_case_template = json.dumps(json.load(fh), indent=2)
    except OSError:
        test_case_template = "(template not found — infer structure from test case inputs)"

    print(f"Loading test cases from {test_cases_dir} ...")
    cases = load_test_cases(test_cases_dir)
    n_allow = sum(tc.expected for tc in cases)
    n_deny = len(cases) - n_allow
    print(f"  test cases : {len(cases)}  (allow={n_allow}, deny={n_deny})")

    print(f"\n[baseline] Evaluating {policy_path} ...")
    summary = evaluate(query_url, cases)
    start_pass_rate = summary.pass_rate
    print(f"  Pass rate  : {summary.pass_rate:.1%}  ({summary.n_passed}/{summary.n_total})")

    if summary.pass_rate == 1.0:
        print("\nAlready at 100% pass rate. Nothing to do.")
        return

    stall_count = 0
    stop_reason = f"max iterations ({max_iter}) reached"
    iteration_log: List[dict] = []

    for iteration in range(1, max_iter + 1):
        if summary.pass_rate == 1.0:
            stop_reason = "SUCCESS — 100% pass rate"
            break
        if stall_count >= stall_limit:
            stop_reason = f"STALLED — {stall_limit} consecutive iterations with no improvement"
            break

        print(f"\n{'='*52}")
        print(f"  Iteration {iteration}/{max_iter}  |  pass rate {summary.pass_rate:.1%}  |  stall {stall_count}/{stall_limit}")
        print(f"{'='*52}")

        # Group failing cases by failure type
        false_denies: List[Tuple[str, dict]] = []
        false_allows: List[Tuple[str, dict]] = []
        for path in summary.failed_cases:
            norm = path.replace(os.sep, "/")
            with open(path) as fh:
                payload = json.load(fh)
            input_doc = payload.get("input", payload) if isinstance(payload, dict) else payload
            if "/allow/" in norm:
                false_denies.append((path, input_doc))
            else:
                false_allows.append((path, input_doc))

        print(f"  False denies: {len(false_denies)}  |  False allows: {len(false_allows)}")

        policy_text = _read_policy(policy_path)
        backup_text = policy_text

        # LLM diagnosis and fix generation
        print("  Calling LLM ...")
        fixes = _call_llm(
            policy_text, false_denies, false_allows,
            test_case_template,
            api_key, openai_base_url, model, temp, top_p,
        )

        if not fixes:
            print("  No fixes returned. Counting as stall.")
            stall_count += 1
            iteration_log.append({"iteration": iteration, "outcome": "no_fixes"})
            continue

        print(f"  {len(fixes)} fix(es) proposed:")
        for i, fix in enumerate(fixes, 1):
            print(f"    {i}. {fix.get('diagnosis', '(no diagnosis)')}")

        # Apply fixes
        new_text, n_applied = _apply_fixes(policy_text, fixes)
        if n_applied == 0:
            print("  No fixes applied (old_text not matched). Counting as stall.")
            stall_count += 1
            iteration_log.append({"iteration": iteration, "outcome": "not_applied"})
            continue

        print(f"  Applied {n_applied}/{len(fixes)} fix(es).")

        with open(policy_path, "w") as fh:
            fh.write(new_text)

        # OPA validation
        ok, err = _validate_opa(policy_path)
        if not ok:
            print(f"  OPA validation failed: {err}")
            print("  Reverting.")
            with open(policy_path, "w") as fh:
                fh.write(backup_text)
            stall_count += 1
            iteration_log.append({"iteration": iteration, "outcome": "opa_invalid"})
            continue

        # Push updated policy to OPA server so evaluations use the new version
        updated_text = _read_policy(policy_path)
        ok, err = _push_policy_to_opa(opa_url, updated_text)
        if not ok:
            print(f"  warning: could not push policy to OPA: {err}")
            print("  Reverting.")
            with open(policy_path, "w") as fh:
                fh.write(backup_text)
            stall_count += 1
            iteration_log.append({"iteration": iteration, "outcome": "opa_push_failed"})
            continue

        # Measure delta
        new_summary = evaluate(query_url, cases)
        delta = new_summary.pass_rate - summary.pass_rate
        sign = "+" if delta >= 0 else ""
        print(f"  New pass rate: {new_summary.pass_rate:.1%}  (delta: {sign}{delta:.1%})")

        if new_summary.pass_rate < summary.pass_rate:
            print("  Regression detected. Reverting.")
            with open(policy_path, "w") as fh:
                fh.write(backup_text)
            _push_policy_to_opa(opa_url, backup_text)
            stall_count += 1
            iteration_log.append({"iteration": iteration, "outcome": "regressed", "delta": delta})
            continue

        iteration_log.append({
            "iteration": iteration,
            "pass_rate": new_summary.pass_rate,
            "delta": delta,
            "n_fixes": n_applied,
            "outcome": "applied",
        })

        stall_count = 0 if delta > 0 else stall_count + 1
        summary = new_summary

    else:
        # Loop ran to completion without a break
        if summary.pass_rate == 1.0:
            stop_reason = "SUCCESS — 100% pass rate"

    # Final summary
    print(f"\n{'='*52}")
    print(f"  FINAL SUMMARY")
    print(f"  Start pass rate : {start_pass_rate:.1%}")
    print(f"  Final pass rate : {summary.pass_rate:.1%}")
    print(f"  Iterations run  : {len(iteration_log)}")
    print(f"  Stop reason     : {stop_reason}")
    if summary.n_failed > 0:
        print(f"\n  Remaining failures ({summary.n_failed}):")
        for path in summary.failed_cases:
            norm = path.replace(os.sep, "/")
            label = "(expected allow)" if "/allow/" in norm else "(expected deny)"
            print(f"    {label}  {path}")
    print(f"{'='*52}")
