# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import subprocess
import json
import os
import csv


def attack(
    output_file_case, output_file_attack, output_file_attack_csv, test_generation_path
):
    with open(output_file_case, "r") as f:
        guidances = json.load(f)
    header = ["Behavior", "Category", "tags", "ContextString", "BehaviorID"]
    attack_targets = []
    for issue in guidances:
        if issue["label"] == "disallow":
            attack_targets.append([issue["user_input"], "", "", "", ""])

    with open(output_file_attack_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(attack_targets)

    try:
        with open("ares.log", "w") as f:
            # result=subprocess.run([test_generation_path+"ares/.venv/bin/python", "test.py"], cwd=test_generation_path+"ares/test_script/", stdout=f, stderr=subprocess.STDOUT, check=True)
            subprocess.run(
                [
                    test_generation_path + "ares/.venv/bin/" + "ares",
                    "evaluate",
                    "example_configs/qwen-owasp-llm-01.yaml",
                    "--generate-only",
                ]
            )  # , stdout=f, stderr=subprocess.STDOUT, check=True)
    except subprocess.CalledProcessError:
        print("jail break partially failed")
    print("ATTACK FINISHED........")
    attack_dicts = {}

    with open(output_file_case, "r") as f:
        attack_dicts = json.load(f)

    attack_prompt_map = {}
    attack_file_list = [
        "encoding_ascii85_attacks_generate",
        "human_jailbreak_generate",
        "encoding_base16_attacks_generate",
        "encoding_base32_attacks_generate",
        "encoding_base64_attacks_generate",
        "encoding_base2048_attacks_generate",
        "encoding_braille_attacks_generate",
        "encoding_ecoji_attacks_generate",
        "encoding_hex_attacks_generate",
        "encoding_morse_attacks_generate",
        "encoding_nato_attacks_generate",
        "encoding_rot13_attacks_generate",
        "encoding_uu_attacks_generate",
        "encoding_zalgo_attacks_generate",
        "direct_requests_generate",
    ]
    for attack_file in attack_file_list:
        attack_prompt_map[attack_file] = {}
        file_path = test_generation_path + "ares/assets/" + attack_file + ".json"
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                attack_prompts = json.load(f)
                for attack_prompt_dict in attack_prompts:
                    if (
                        attack_prompt_dict["goal"]
                        not in attack_prompt_map[attack_file].keys()
                    ):
                        attack_prompt_map[attack_file][attack_prompt_dict["goal"]] = []
                    attack_prompt_map[attack_file][attack_prompt_dict["goal"]].append(
                        attack_prompt_dict["prompt"]
                    )

    for attack_dict_index in range(len(attack_dicts)):
        attack_dicts[attack_dict_index]["attack_conditions"] = {}
        for attack_file in attack_file_list:
            # print(attack_file)
            attack_dicts[attack_dict_index]["attack_conditions"][attack_file] = []
            if attack_dicts[attack_dict_index]["label"] == "disallow":
                disallow_condition = attack_dicts[attack_dict_index]["user_input"]
                # print(attack_prompt_map[attack_file].keys())
                attack_dicts[attack_dict_index]["attack_conditions"][
                    attack_file
                ].extend(attack_prompt_map[attack_file][disallow_condition])
    with open(output_file_attack, "w") as f:
        json.dump(attack_dicts, f, indent=4)


if __name__ == "__main__":
    print("placeholder")
