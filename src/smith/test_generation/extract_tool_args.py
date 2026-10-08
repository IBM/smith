# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""
Process test cases by calling the agent's /extract_tool_call endpoint
to extract tool name and arguments for each test case.

This is a simplified version of RagChatbot_MCPServer/smith/process_test_batch.py
that uses the agent endpoint instead of reimplementing the chat loop.
"""

import os
import json
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


def resolve_concurrency():
    raw = os.getenv("TRANSLATION_CONCURRENCY", "-1")
    try:
        requested = int(raw)
    except ValueError:
        print(
            f"  Invalid TRANSLATION_CONCURRENCY={raw!r}, sending one request at a time"
        )
        return 1
    return requested if requested > 1 else 1


def fetch_tool_call(agent_url, prompt, user_profile):
    response = requests.post(
        f"{agent_url}/extract_tool_call",
        json={"question": prompt, "user_profile": user_profile},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def run_extract_tool_args(test_case_path, agent_url):
    """Process all test cases by calling /extract_tool_call endpoint."""
    labels = ["allow", "disallow"]
    miscalled_cases = []
    total_processed = 0
    concurrency = resolve_concurrency()

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

    for label in labels:
        label_path = os.path.join(test_case_path, label, "*")
        files = sorted(glob.glob(label_path))
        print(f"\nProcessing {len(files)} {label} cases...")

        pending = []
        for file_path in files:
            with open(file_path, "r") as f:
                test_case = json.load(f)

            # Skip cases already translated. `args` is added exactly once,
            if "args" in test_case["input"]:
                continue

            pending.append(
                {
                    "file_path": file_path,
                    "test_case": test_case,
                    "prompt": test_case["input"]["extensions"]["agent"]["input"],
                    "user_profile": test_case["input"]["extensions"]["subject"],
                }
            )

        if not pending:
            continue

        def _work(item):
            try:
                return (
                    fetch_tool_call(agent_url, item["prompt"], item["user_profile"]),
                    None,
                )
            except Exception as e:
                return None, e

        results = [None] * len(pending)
        if concurrency == 1:
            for pos, item in enumerate(pending):
                results[pos] = _work(item)
        else:
            print(f"  Dispatching {len(pending)} requests, {concurrency} at a time...")
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = {
                    pool.submit(_work, item): pos for pos, item in enumerate(pending)
                }
                done = 0
                for fut in as_completed(futures):
                    results[futures[fut]] = fut.result()
                    done += 1
                    if done % 10 == 0 or done == len(pending):
                        print(f"  Received {done}/{len(pending)} responses")

        for item, (result, error) in zip(pending, results):
            file_path = item["file_path"]
            test_case = item["test_case"]

            if error is not None:
                print(f"  Error calling /extract_tool_call for {file_path}: {error}")
                continue

            tool_name = result.get("tool_name", "other")
            # `arguments` here is the agent's /extract_tool_call response contract.
            tool_args = result.get("arguments", {})
            assigned_tool = test_case["input"]["name"]
            total_processed += 1
            test_case["input"]["name"] = tool_name
            test_case["input"]["args"] = tool_args
            with open(file_path, "w") as f:
                json.dump(test_case, f, indent=4)

            is_other = tool_name.lower() == "other"
            if is_other or tool_name != assigned_tool:
                miscalled_cases.append(
                    {
                        "file_path": file_path,
                        "label": label,
                        "assigned_tool": assigned_tool,
                        "actual_tool": tool_name,
                        "agent_input": item["prompt"],
                        "actual_args": tool_args,
                    }
                )
                print(
                    f"  [MISMATCH] {file_path}: assigned={assigned_tool}, actual={tool_name}, moving to misclassified"
                )
                dest = os.path.join(
                    misclassified_path, label, os.path.basename(file_path)
                )
                os.rename(file_path, dest)

    miscalled_output = os.path.join(test_case_path, "miscalled_cases.json")
    with open(miscalled_output, "w") as f:
        json.dump(miscalled_cases, f, indent=4)

    print(
        f"\nDone. Processed: {total_processed}, Mismatches removed: {len(miscalled_cases)}"
    )
    print(f"Saved miscalled cases to: {miscalled_output}")
