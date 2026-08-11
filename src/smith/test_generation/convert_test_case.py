# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
from dotenv import load_dotenv

load_dotenv()


def _convert_var(value, reference_value):
    """Convert a var to the correct type based on system_vars.json reference."""
    if isinstance(reference_value, list):
        if isinstance(value, list):
            return value
        return [value]
    if isinstance(reference_value, int):
        return int(value)
    if isinstance(reference_value, float):
        return float(value)
    return value


def translate_case(
    output_file_cases,
    test_case_template_file,
    output_file_ready_cases,
    output_file_attack,
    output_file_attack_promptfoo,
    system_vars=None,
    selected_tools=None,
):
    if system_vars is None:
        system_vars = {}

    test_cases_translated = {}
    test_cases_translated["allow"] = []
    test_cases_translated["disallow"] = []
    test_cases_translated["ares_malicious"] = []
    test_cases_translated["promptfoo_malicious"] = []
    test_cases_translated["bypass_malicious"] = []
    test_cases_translated["bypass_benign"] = []

    with open(output_file_cases, "r") as f:
        test_cases = json.load(f)

    if output_file_attack:
        test_cases = merge_with_ares(test_cases, output_file_attack)
    if output_file_attack_promptfoo:
        test_cases = merge_with_promptfoo(test_cases, output_file_attack_promptfoo)

    if selected_tools:
        before_count = len(test_cases)
        test_cases = [tc for tc in test_cases if tc.get("action") in selected_tools]
        filtered = before_count - len(test_cases)
        if filtered:
            print(
                f"Filtered {filtered} test cases not targeting selected tools: {sorted(selected_tools)}"
            )

    for test_case in test_cases:
        filled = _fill_template(test_case, test_case_template_file, system_vars)
        test_cases_translated[test_case["label"]].append(filled)

    test_cases = test_case_field_mapping(test_cases_translated, output_file_ready_cases)
    return test_cases


def _fill_template(test_case, test_case_template_file, system_vars):
    """Clone the case template and inject a single abstract case's fields.

    Shared by the main convert path (``translate_case``) and the bypass convert
    path (``convert_bypass_case``) so both fill the template identically.
    """
    with open(test_case_template_file, "r") as f:
        test_case_template = json.load(f)
    test_case_template["name"] = test_case["action"]
    test_case_template["extensions"]["agent"]["input"] = test_case["user_input"]
    for key, value in test_case["system_variables"].items():
        if key in system_vars:
            value = _convert_var(value, system_vars[key])
        if isinstance(value, str) and value.lower() in ("true", "false"):
            value = value.lower() == "true"
        test_case_template["extensions"]["subject"][key] = value
    return test_case_template


def convert_bypass_case(
    bypass_cases_file,
    test_case_template_file,
    output_file_ready_cases,
    system_vars=None,
):
    """Convert only bypass cases into ``bypass_test_case*.json`` files. Independent of ``translate_case``"""
    if system_vars is None:
        system_vars = {}

    with open(bypass_cases_file, "r") as f:
        bypass_cases = json.load(f)

    test_cases_translated = {"bypass_malicious": [], "bypass_benign": []}
    for test_case in bypass_cases:
        # Skip cases without a recognized bypass label rather than guessing a
        # direction — an unlabeled case has no defined intended decision.
        label = test_case.get("label")
        if label not in test_cases_translated:
            print(f"  Skipping bypass case with missing/unknown label: {label!r}")
            continue
        filled = _fill_template(test_case, test_case_template_file, system_vars)
        test_cases_translated[label].append(filled)

    test_case_field_mapping(test_cases_translated, output_file_ready_cases)
    return test_cases_translated


def merge_with_ares(test_cases, output_file_attack):
    if not output_file_attack or not os.path.exists(output_file_attack):
        print(
            f"ARES attack file not found ({output_file_attack}); "
            "skipping ARES merge (nothing was generated for this run)."
        )
        return test_cases
    with open(output_file_attack, "r") as f:
        attack_cases = json.load(f)
    for test_cluster in attack_cases:

        formatted_test_case = {}
        formatted_test_case["action"] = test_cluster["action"]
        formatted_test_case["condition"] = test_cluster["condition"]
        formatted_test_case["system_variables"] = test_cluster["system_variables"]
        formatted_test_case["label"] = "ares_malicious"

        for attack_kind in test_cluster["attack_conditions"].keys():
            if len(test_cluster["attack_conditions"][attack_kind]) > 0:
                for attack_case in test_cluster["attack_conditions"][attack_kind]:
                    formatted_test_case["user_input"] = attack_case
                    test_cases.append(dict(formatted_test_case))

    return test_cases


def merge_with_promptfoo(test_cases, output_file_attack_promptfoo):
    if not output_file_attack_promptfoo or not os.path.exists(
        output_file_attack_promptfoo
    ):
        print(
            f"Promptfoo attack file not found ({output_file_attack_promptfoo}); "
            "skipping promptfoo merge (nothing was generated for this run)."
        )
        return test_cases
    with open(output_file_attack_promptfoo, "r") as f:
        attack_cases = json.load(f)
    for test_cluster in attack_cases:
        formatted_test_case = {}
        formatted_test_case["action"] = test_cluster.get("action", "Promptfoo")
        formatted_test_case["system_variables"] = test_cluster["system_variables"]
        formatted_test_case["label"] = "promptfoo_malicious"
        formatted_test_case["user_input"] = test_cluster["user_input"]
        test_cases.append(formatted_test_case)
    return test_cases


def test_case_field_mapping(test_cases_translated, output_file_ready_cases):
    """Write each translated case to <output_file_ready_cases><label>/<prefix><N>.json."""
    for condition in test_cases_translated.keys():
        test_cases = test_cases_translated[condition]
        if condition == "promptfoo_malicious":
            output_dir = "disallow"
            prefix = "promptfoo_test_case"
        elif condition == "bypass_malicious":
            output_dir = "disallow"
            prefix = "bypass_test_case"
        elif condition == "bypass_benign":
            output_dir = "allow"
            prefix = "bypass_test_case"
        else:
            output_dir = condition
            prefix = "test_case"
        for test_case_index in range(len(test_cases)):
            test_case_template_final = {}
            test_case_template_final["input"] = test_cases[test_case_index]
            os.makedirs(output_file_ready_cases + output_dir, exist_ok=True)
            with open(
                output_file_ready_cases
                + output_dir
                + "/"
                + prefix
                + str(test_case_index)
                + ".json",
                "w",
            ) as f:
                json.dump(test_case_template_final, f, indent=4)
    print("test case generation finished.")
