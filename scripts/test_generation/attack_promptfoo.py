import subprocess
import yaml
import json
import os
from dotenv import load_dotenv

load_dotenv()


def run_attack(base_skill_url, test_generation_path, output_promptfoo):
    promptfoo_config = str(os.getenv("PROMPTFOO_CONFIG_FILE"))
    promptfoo_config = base_skill_url + promptfoo_config
    try:
        result = subprocess.run(
            [
                "promptfoo",
                "redteam",
                "generate",
                "--config",
                promptfoo_config,
                "-o",
                output_promptfoo,
            ],
            cwd=test_generation_path + "promptfoo/",
            check=True,
        )
    except subprocess.CalledProcessError:
        print("promptfoo finished")
    print("PROMPTFOO ATTACK FINISHED........")


def read_test_cases(output_file_attack_promptfoo, output_promptfoo):
    test_cases = []
    with open(output_promptfoo) as f:
        data = yaml.safe_load(f)
    for case in data["tests"]:
        test_case_dict = {}
        test_case_dict["label"] = "malicious_promptfoo"
        test_case_dict["user_input"] = case["vars"]["prompt"]
        test_case_dict["system_variables"] = {}
        test_cases.append(test_case_dict)
    with open(output_file_attack_promptfoo, "w") as f:
        json.dump(test_cases, f, indent=4)


def create_promptfoo_cases(
    base_skill_url, output_promptfoo, output_file_attack_promptfoo, test_generation_path
):
    run_attack(base_skill_url, test_generation_path, output_promptfoo)
    read_test_cases(output_file_attack_promptfoo, output_promptfoo)
