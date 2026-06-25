"""
Cross-validate failed test cases against guidance to identify mislabeled cases.

Reads failed test cases from policy testing results, checks each against the
guidance using an LLM, and outputs a structured JSON report with suspected
mislabels and reasoning.

Usage via CLI:
    smith --flag cross_validate
"""

import json
import re
import os
import httpx
from openai import OpenAI


SYSTEM_PROMPT = """You are a policy test case auditor. Your job is to determine whether a failed test case is mislabeled or if the policy has a bug.

You will be given:
1. The policy guidance rules (the source of truth)
2. The system variables and their possible values
3. A test case that FAILED policy testing (the policy decision did not match the expected label)

For each failed test case, analyze:
- The user's role and the tool being called
- The arguments being passed
- Whether the guidance allows or denies this specific combination

Then determine:
- If the test case label is WRONG (mislabeled during generation), OR
- If the test case label is CORRECT but the policy has a bug

Respond ONLY in JSON format:
{"label_correct": true/false, "confidence": 0.0 to 1.0, "reason": "brief explanation of why the label is correct or incorrect based on the guidance", "suggested_action": "keep" or "move_to_allow" or "move_to_disallow" or "remove"}

- "keep" = the label is correct, the policy needs fixing
- "move_to_allow" = the case is mislabeled, it should be in the allow folder
- "move_to_disallow" = the case is mislabeled, it should be in the disallow folder
- "remove" = the case is ambiguous or invalid, best to remove it"""


USER_PROMPT_TEMPLATE = """## Guidance Rules
{guidance}

## System Variables
{system_vars}

## Failed Test Case
File: {file_path}
Expected label: {expected_label} (based on folder: allow/ or disallow/)
Actual policy decision: {actual_decision}

Test case content:
- Tool: {tool_name}
- User role: {user_role}
- Arguments: {arguments}
- Agent input (user prompt): {agent_input}

Based on the guidance rules above, is the expected label ("{expected_label}") correct for this test case?"""


def parse_failures(failures_file):
    """Parse score_test_failures.txt into structured list."""
    failures = []
    with open(failures_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith("[FAIL"):
                continue

            expected_allow = "expected_allow: true" in line
            actual_allow = "allow: true" in line.split("test_case:")[0]

            path_match = re.search(r"test_case:\s*(.+?)\]", line)
            if path_match:
                raw_path = path_match.group(1).strip()
                resolved_path = os.path.normpath(raw_path)
                failures.append({
                    "path": resolved_path,
                    "expected_label": "allow" if expected_allow else "disallow",
                    "actual_decision": "allow" if "\"result\":true" in line else "deny",
                })
    return failures


def load_test_case(path):
    """Load a test case JSON and extract key fields."""
    with open(path, "r") as f:
        data = json.load(f)

    inp = data.get("input", data)
    subject = inp.get("extensions", {}).get("subject", {})
    agent = inp.get("extensions", {}).get("agent", {})

    return {
        "tool_name": inp.get("name", "unknown"),
        "user_role": subject.get("user_role", []),
        "arguments": inp.get("arguments", {}),
        "agent_input": agent.get("input", ""),
    }


def cross_validate_failed_cases(
    failures_file,
    guidance_file,
    system_var_file,
    output_file,
    api_key,
    openai_base_url,
    model,
    temp,
    top_p,
):
    """
    Cross-validate failed test cases against guidance.
    Outputs a JSON report with suspected mislabels and reasoning.
    """
    if not os.path.exists(failures_file):
        print(f"No failures file found at: {failures_file}")
        print("Run 'smith --flag policy_testing' first to generate test results.")
        return

    failures = parse_failures(failures_file)
    if not failures:
        print("No failed test cases found. All tests passed!")
        return

    print(f"Found {len(failures)} failed test cases. Cross-validating against guidance...")

    with open(guidance_file, "r") as f:
        guidance = f.read()

    with open(system_var_file, "r") as f:
        system_vars = f.read()

    http_client = httpx.Client(verify=False, timeout=300.0)
    client = OpenAI(api_key=api_key, base_url=openai_base_url, http_client=http_client)

    results = []
    mislabeled_count = 0
    policy_issue_count = 0

    for i, failure in enumerate(failures):
        path = failure["path"]
        if not os.path.exists(path):
            print(f"  [{i+1}/{len(failures)}] SKIP (file not found): {os.path.basename(path)}")
            continue

        case_data = load_test_case(path)

        user_prompt = USER_PROMPT_TEMPLATE.format(
            guidance=guidance,
            system_vars=system_vars,
            file_path=os.path.basename(path),
            expected_label=failure["expected_label"],
            actual_decision=failure["actual_decision"],
            tool_name=case_data["tool_name"],
            user_role=case_data["user_role"],
            arguments=json.dumps(case_data["arguments"]),
            agent_input=case_data["agent_input"][:500],
        )

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temp,
                top_p=top_p,
            )

            llm_output = response.choices[0].message.content.strip()

            match = re.search(r"```json\s*(.*?)```", llm_output, re.DOTALL)
            if match:
                llm_output = match.group(1).strip()

            result = json.loads(llm_output)

            label_correct = result.get("label_correct", True)
            if not label_correct:
                mislabeled_count += 1
            else:
                policy_issue_count += 1

            results.append({
                "path": path,
                "filename": os.path.basename(path),
                "expected_label": failure["expected_label"],
                "actual_policy_decision": failure["actual_decision"],
                "tool_name": case_data["tool_name"],
                "user_role": case_data["user_role"],
                "arguments": case_data["arguments"],
                "label_correct": label_correct,
                "confidence": float(result.get("confidence", 0.5)),
                "reason": result.get("reason", ""),
                "suggested_action": result.get("suggested_action", "keep"),
            })

            status = "POLICY ISSUE" if label_correct else "MISLABELED"
            print(f"  [{i+1}/{len(failures)}] {status}: {os.path.basename(path)} — {result.get('reason', '')[:80]}")

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            results.append({
                "path": path,
                "filename": os.path.basename(path),
                "expected_label": failure["expected_label"],
                "actual_policy_decision": failure["actual_decision"],
                "tool_name": case_data["tool_name"],
                "user_role": case_data["user_role"],
                "arguments": case_data["arguments"],
                "label_correct": True,
                "confidence": 0.5,
                "reason": f"Failed to parse LLM response: {str(e)}",
                "suggested_action": "keep",
            })
            print(f"  [{i+1}/{len(failures)}] UNCERTAIN: {os.path.basename(path)} — parse error")

        except Exception as e:
            print(f"  [{i+1}/{len(failures)}] ERROR: {os.path.basename(path)} — {str(e)}")
            results.append({
                "path": path,
                "filename": os.path.basename(path),
                "expected_label": failure["expected_label"],
                "actual_policy_decision": failure["actual_decision"],
                "tool_name": case_data["tool_name"],
                "user_role": case_data["user_role"],
                "arguments": case_data["arguments"],
                "label_correct": True,
                "confidence": 0.0,
                "reason": f"LLM call failed: {str(e)}",
                "suggested_action": "keep",
            })

    report = {
        "summary": {
            "total_failed": len(failures),
            "analyzed": len(results),
            "mislabeled": mislabeled_count,
            "policy_issue": policy_issue_count,
        },
        "cases": results,
    }

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nCross-validation complete.")
    print(f"  Total failed: {len(failures)}")
    print(f"  Mislabeled:   {mislabeled_count}")
    print(f"  Policy issue: {policy_issue_count}")
    print(f"  Report saved: {output_file}")
