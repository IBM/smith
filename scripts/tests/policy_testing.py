# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import subprocess
import os
from dotenv import load_dotenv

load_dotenv()


def run_policy_evaluation():
    """
    Run all policy tests using the Makefile in the project root.
    Saves outputs in the feedback directory under tmp.
    """
    base_url = os.getenv("BASE_URL") + "scripts/"
    if not base_url:
        raise ValueError("BASE_URL not provided")

    # Define project root and output paths
    project_root = os.path.abspath(base_url)
    makefile_path = os.path.join(project_root, "Makefile")
    if not os.path.exists(makefile_path):
        raise FileNotFoundError(f"Makefile not found at {makefile_path}")

    print("Running policy evaluation tests via Makefile...")
    print(f"Project root: {project_root}")

    # Run tests using Makefile
    try:
        subprocess.run(["make", "test"], cwd=project_root, check=True)
        print("Policy evaluation tests completed successfully.")
    except subprocess.CalledProcessError:
        print(
            "Policy evaluation tests failed. Check test outputs under 'tests/' for details."
        )
    content = ""

    test_path = base_url + os.getenv("TEST_PATH")
    test_results_path = test_path + os.getenv("TEST_RESULT_PATH")
    with open(test_results_path, "r") as file:
        content = str(file.read())
    return content


if __name__ == "__main__":
    run_policy_evaluation()
