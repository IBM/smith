"""
Process test cases by calling the agent's /extract_tool_call endpoint
to extract tool name and arguments for each test case.

This is a simplified version of RagChatbot_MCPServer/smith/process_test_batch.py
that uses the agent endpoint instead of reimplementing the chat loop.
"""

import os
import json
import glob
import requests


def run_extract_tool_args(test_case_path, agent_url):
    """Process all test cases by calling /extract_tool_call endpoint."""
    labels = ["allow", "disallow"]
    miscalled_cases = []
    total_processed = 0

    generated_cases_path = os.path.join(test_case_path, "wrong_cases", "mcp_unrelated")
    misclassified_path = os.path.join(test_case_path, "wrong_cases", "misclassified")
    for label in labels:
        generated_label_path = os.path.join(generated_cases_path, label)
        os.makedirs(generated_label_path, exist_ok=True)
        os.makedirs(os.path.join(misclassified_path, label), exist_ok=True)
        label_path = os.path.join(test_case_path, label, "*")
        files = sorted(glob.glob(label_path))
        for file_path in files:
            with open(file_path, "r") as f:
                test_case = json.load(f)
            if test_case["input"].get("name", "").lower() == "other":
                dest = os.path.join(generated_label_path, os.path.basename(file_path))
                os.rename(file_path, dest)
                # print(f"  [OTHER] Moved {file_path} -> {dest}")

    for label in labels:
        label_path = os.path.join(test_case_path, label, "*")
        files = sorted(glob.glob(label_path))
        print(f"\nProcessing {len(files)} {label} cases...")

        for file_path in files:
            with open(file_path, "r") as f:
                test_case = json.load(f)

            prompt = test_case["input"]["extensions"]["agent"]["input"]
            user_profile = test_case["input"]["extensions"]["subject"]

            try:
                response = requests.post(
                    f"{agent_url}/extract_tool_call",
                    json={"question": prompt, "user_profile": user_profile},
                    timeout=120,
                )
                response.raise_for_status()
                result = response.json()
            except Exception as e:
                print(f"  Error calling /extract_tool_call for {file_path}: {e}")
                continue

            tool_name = result.get("tool_name", "other")
            tool_args = result.get("arguments", {})
            assigned_tool = test_case["input"]["name"]
            total_processed += 1

            if assigned_tool.lower() == "promptfoo":
                test_case["input"]["name"] = tool_name
                test_case["input"]["arguments"] = tool_args
                with open(file_path, "w") as f:
                    json.dump(test_case, f, indent=4)
            elif tool_name != assigned_tool:
                miscalled_cases.append(
                    {
                        "file_path": file_path,
                        "label": label,
                        "assigned_tool": assigned_tool,
                        "actual_tool": tool_name,
                        "agent_input": prompt,
                        "actual_args": tool_args,
                    }
                )
                print(
                    f"  [MISMATCH] {file_path}: assigned={assigned_tool}, actual={tool_name}, moving to misclassified"
                )
                dest = os.path.join(misclassified_path, label, os.path.basename(file_path))
                os.rename(file_path, dest)
            else:
                test_case["input"]["arguments"] = tool_args
                with open(file_path, "w") as f:
                    json.dump(test_case, f, indent=4)

    miscalled_output = os.path.join(test_case_path, "miscalled_cases.json")
    with open(miscalled_output, "w") as f:
        json.dump(miscalled_cases, f, indent=4)

    print(
        f"\nDone. Processed: {total_processed}, Mismatches removed: {len(miscalled_cases)}"
    )
    print(f"Saved miscalled cases to: {miscalled_output}")
