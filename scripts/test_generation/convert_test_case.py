import json
import os
from dotenv import load_dotenv
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
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
):
    if system_vars is None:
        system_vars = {}

    test_cases_translated = {}
    test_cases_translated["allow"] = []
    test_cases_translated["disallow"] = []
    test_cases_translated["ares_malicious"] = []
    test_cases_translated["promptfoo_malicious"] = []

    with open(output_file_cases, "r") as f:
        test_cases = json.load(f)

    test_cases = merge_with_ares(test_cases, output_file_attack)
    test_cases = merge_with_promptfoo(test_cases, output_file_attack_promptfoo)

    test_case_template = {}
    for test_case in test_cases:
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
        test_cases_translated[test_case["label"]].append(test_case_template)

    test_cases = test_case_field_mapping(test_cases_translated, output_file_ready_cases)
    return test_cases


def merge_with_ares(test_cases, output_file_attack):
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
    with open(output_file_attack_promptfoo, "r") as f:
        attack_cases = json.load(f)
    for test_cluster in attack_cases:
        formatted_test_case = {}
        formatted_test_case["action"] = "Promptfoo"
        formatted_test_case["system_variables"] = test_cluster["system_variables"]
        formatted_test_case["label"] = "promptfoo_malicious"
        formatted_test_case["user_input"] = test_cluster["user_input"]
        test_cases.append(formatted_test_case)
    return test_cases


def test_case_field_mapping(test_cases_translated, output_file_ready_cases):
    for condition in test_cases_translated.keys():
        test_cases = test_cases_translated[condition]
        for test_case_index in range(len(test_cases)):
            test_case_template_final = {}
            test_case_template_final["input"] = test_cases[test_case_index]
            os.makedirs(output_file_ready_cases + condition, exist_ok=True)
            with open(
                output_file_ready_cases
                + condition
                + "/test_case"
                + str(test_case_index)
                + ".json",
                "w",
            ) as f:
                json.dump(test_case_template_final, f, indent=4)
    print("test case generation finished.")
