# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import os
from dotenv import load_dotenv
import subprocess

load_dotenv()


def create_regal_suggestion(policy_path, regal_suggestion_path):
    subprocess.run(
        [
            "regal lint "
            + policy_path
            + " | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g' > "
            + regal_suggestion_path
        ],
        shell=True,
    )
    content = ""
    with open(regal_suggestion_path, "r") as file:
        content = str(file.read())
    return content


if __name__ == "__main__":
    policy_dir = os.getenv("POLICY_DIR")
    regal_suggestion_path = os.getenv("REGAL_SUGGESTION_PATH")
    create_regal_suggestion(policy_dir, regal_suggestion_path)
