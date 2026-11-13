# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Check the policy-generation guide's final decision against real OPA.

The Rego scaffold is read directly from the guide. Only tool-specific grant
and deny examples are inserted; the final authorization rule runs unchanged.
No models or credentials are needed, and every file is under tmp_path.
"""

import json
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def guidance_policy(tmp_path, requires_opa_binary):
    guide = (
        Path(__file__).resolve().parents[2]
        / "opa_policy/policy_creation/opa_policy_creation.md"
    )
    scaffold = guide.read_text().split("```rego\n", 1)[1].split("```", 1)[0]
    scaffold = scaffold.replace(
        "# permitted if { ... }\n# deny contains msg if { ... }",
        'permitted if { input.name == "get_events"; "faculty" in subject.user_role }\n'
        'deny contains "limit exceeds 4" if { args.limit > 4 }',
    )
    policy = tmp_path / "policy.rego"
    policy.write_text(scaffold)
    return policy


@pytest.mark.parametrize(
    "name,limit,roles,expected",
    [
        ("get_events", 4, ["faculty"], True),
        ("get_events", 100, ["faculty"], False),
        ("get_events", 4, ["guest"], False),
        ("unknown_tool", 4, ["faculty"], False),
    ],
)
def test_grants_require_a_matching_scope_and_no_denies(
    guidance_policy, name, limit, roles, expected
):
    result = subprocess.run(
        [
            "opa",
            "eval",
            "--format=json",
            "--stdin-input",
            "--data",
            str(guidance_policy),
            "data.mcp.policies.allow",
        ],
        input=json.dumps(
            {
                "name": name,
                "args": {"limit": limit},
                "extensions": {"subject": {"user_role": roles}},
            }
        ),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert json.loads(result.stdout)["result"][0]["expressions"][0]["value"] is expected


def test_guidance_with_only_grants_has_a_defined_empty_deny_set(guidance_policy):
    guidance_policy.write_text(
        guidance_policy.read_text().replace(
            'deny contains "limit exceeds 4" if { args.limit > 4 }', "deny := set()"
        )
    )
    result = subprocess.run(
        [
            "opa",
            "eval",
            "--format=json",
            "--stdin-input",
            "--data",
            str(guidance_policy),
            "data.mcp.policies.allow",
        ],
        input=json.dumps(
            {
                "name": "get_events",
                "args": {},
                "extensions": {"subject": {"user_role": ["faculty"]}},
            }
        ),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert json.loads(result.stdout)["result"][0]["expressions"][0]["value"] is True
