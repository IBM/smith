# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import subprocess
import os
from dotenv import load_dotenv


def run_policy_evaluation(base_url, test_result_path):
    """
    Run all policy tests using the Makefile in the project root.
    Saves outputs in the feedback directory under tmp.
    """

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
        subprocess.run(
            ["make", "test"], cwd=project_root, check=True, stdout=subprocess.DEVNULL
        )
        print("Policy evaluation tests completed successfully.")
    except subprocess.CalledProcessError:
        print(
            "Policy evaluation tests failed. Check test outputs under 'tests/' for details."
        )
    content = ""
    with open(test_result_path, "r") as file:
        content = str(file.read())
    print(content)
    return content


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    base_url = os.getenv("BASE_URL")
    out_dir = base_url + os.getenv("TEST_OUTPUT_DIR", "references/scorecard/")
    test_results_path = out_dir + os.getenv("TEST_RESULT_PATH", "scorecard_summary.txt")
    run_policy_evaluation(base_url, test_results_path)
