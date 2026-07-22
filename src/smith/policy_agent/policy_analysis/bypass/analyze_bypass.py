# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import os
import re
import json
from pathlib import Path

import httpx
from openai import OpenAI
from dotenv import load_dotenv

from smith.policy_agent.policy_analysis.bypass.schema import (
    BypassVector,
    BypassReport,
)

load_dotenv()

VALID_CATEGORIES = {
    "omitted_field",
    "type_confusion",
    "malformed_value",
    "keyword_evasion",
}

MAX_BYPASS_PARSE_ATTEMPTS = 3


def detect_bypass_vectors(
    api_key,
    output_dir,
    openai_base_url,
    policy_path,
    model,
    temp,
    top_p,
    guidance_file,
    tool_definitions=None,
    system_vars=None,
):
    """Detect guidance-vs-policy divergences in ``policy_path``; save reports.

    Compares the intended behavior in ``guidance_file`` against what the policy
    actually enforces. Returns a ``BypassReport``. Raises ``FileNotFoundError`` if
    the policy is missing (callers should guard for a missing/empty policy before
    invoking).
    """
    if not os.path.exists(policy_path):
        raise FileNotFoundError(f"Policy file not found: {policy_path}")

    with open(policy_path, "r", encoding="utf-8") as f:
        rego_policy = f.read()

    guidance_text = ""
    if guidance_file and os.path.exists(guidance_file):
        with open(guidance_file, "r", encoding="utf-8") as f:
            guidance_text = f.read()
    else:
        print(
            f"  Warning: guidance file not found ({guidance_file}); bypass "
            "analysis will fall back to the policy's evident intent only."
        )

    schema_json_str = json.dumps(BypassVector.model_json_schema(), indent=2)
    tool_ctx = json.dumps(tool_definitions, indent=2) if tool_definitions else "(none)"
    sysvar_ctx = json.dumps(system_vars, indent=2) if system_vars else "(none)"
    guidance_ctx = guidance_text if guidance_text else "(guidance unavailable)"

    system_instruction = f"""
You are a security analyst specialized in OPA Rego access-control policies for AI/MCP agents.
You are given the GUIDANCE (the natural-language rules the policy is meant to enforce — the
ground truth of intent), the complete Rego POLICY (its implementation), the available tool
definitions, and the session/system variables a request can carry.

Your task: find where the POLICY DIVERGES FROM THE GUIDANCE — concrete requests for which the
policy's composed allow/deny decision disagrees with what the guidance intends. Reason about
the whole policy together (rules depend on one another), and about each guidance rule and
whether the policy faithfully enforces it. Report divergences in BOTH directions:

- guidance_deny_policy_allow: the guidance forbids the request, but the policy ALLOWS it
  (a prohibited request slips through — the intended decision is "disallow").
- guidance_allow_policy_deny: the guidance permits the request, but the policy DENIES it
  (a legitimate request is wrongly blocked — the intended decision is "allow").

Only the request's own inputs are caller-controllable: input.arguments.* and the natural-
language input.extensions.agent.input. The subject/session fields (input.extensions.subject.*,
e.g. role, team, approval, claims) are set by a trusted upstream identity layer and are NOT
attacker-controllable — never treat setting a subject field as a divergence.

Classify each divergence by the MECHANISM that causes it:
- omitted_field: a rule references a field with no default / existence check, so omitting the
  field from the request evades the guard.
- type_confusion: a numeric/boolean comparison without a type assertion, evadable by sending
  the value as a different type (e.g. a string).
- malformed_value: a substring/regex match on structured data (email, URL, path) that a
  malformed but accepted value slips past.
- keyword_evasion: an exact keyword/substring match evadable by casing, splitting, spacing,
  or encoding.

For each divergence set `direction` (one of the two above), `guidance_rule` (quote or number
the specific guidance rule it contradicts), `rules_involved` (the policy rule(s)), the `field`,
a one-line `reason`, an `exploit_strategy` a test-case generator can turn into a request, and
a `severity`.

GUIDANCE (intended behavior — the ground truth):
{guidance_ctx}

Tool definitions (request argument shapes → input.arguments.*):
{tool_ctx}

System variables (subject fields → input.extensions.subject.*):
{sysvar_ctx}

Output a JSON array; each element must follow this schema:
{schema_json_str}

Output only JSON. No Markdown, no explanations.
"""

    http_client = httpx.Client(verify=False, timeout=300.0)
    client = OpenAI(api_key=api_key, base_url=openai_base_url, http_client=http_client)

    # Query the model, retrying on malformed JSON. Each attempt is a fresh model
    # call so a transient bad-format response can be recovered instead of being
    # written out as a silent empty report.
    report = BypassReport(vectors=[])
    for attempt in range(1, MAX_BYPASS_PARSE_ATTEMPTS + 1):
        print(
            f"Sending policy to model for bypass vector detection "
            f"(attempt {attempt}/{MAX_BYPASS_PARSE_ATTEMPTS})..."
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": rego_policy},
            ],
            max_tokens=30000,
            temperature=temp,
            top_p=top_p,
        )

        llm_output = response.choices[0].message.content.strip()
        match = re.search(r"```json\s*(.*?)```", llm_output, re.DOTALL)
        if match:
            llm_output = match.group(1).strip()

        try:
            raw = json.loads(llm_output)
            vectors = []
            for item in raw:
                if item.get("category") not in VALID_CATEGORIES:
                    continue
                vectors.append(BypassVector(**item))
            report = BypassReport(vectors=vectors)
            break
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            print("Error parsing bypass LLM output:", e)
            print("LLM output was:", llm_output)
            if attempt < MAX_BYPASS_PARSE_ATTEMPTS:
                print(
                    f"Bypass analysis returned malformed JSON "
                    f"(attempt {attempt}/{MAX_BYPASS_PARSE_ATTEMPTS}); "
                    "re-running the model..."
                )
            else:
                print(
                    "Bypass analysis failed to return valid JSON after "
                    f"{MAX_BYPASS_PARSE_ATTEMPTS} attempts; returning an empty "
                    "report."
                )
                report = BypassReport(vectors=[])

    os.makedirs(output_dir, exist_ok=True)
    json_file = os.path.join(output_dir, "bypass_report.json")
    Path(json_file).write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"Bypass report (JSON) saved to {json_file}")

    md_file = os.path.join(output_dir, "bypass_report.md")
    Path(md_file).write_text(report.to_markdown(), encoding="utf-8")
    print(f"Bypass report (Markdown) saved to {md_file}")

    print(f"Detected {len(report.vectors)} bypass vector(s).")
    return report
