# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import os
import re
from dotenv import load_dotenv
import subprocess

load_dotenv()

# CSI escape sequences. Regal colourises its report, and the text is both printed
# and fed to an LLM, so the codes are stripped before either sees it.
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# `regal lint` exit codes: 0 = no violations, 3 = violations found. Anything else
# (notably 127, binary not found) means the linter did not run.
_REGAL_RAN = (0, 3)


def create_regal_suggestion(policy_path, regal_suggestion_path):
    try:
        result = subprocess.run(
            ["regal", "lint", policy_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        content = f"regal lint could not be run: {exc}"
    else:
        if result.returncode in _REGAL_RAN:
            content = _ANSI_ESCAPE.sub("", result.stdout)
        else:
            # Report the failure instead of an empty file, which would read as
            # "the policy has no style issues".
            detail = (result.stderr or result.stdout).strip()
            content = (
                f"regal lint failed (exit {result.returncode}). "
                "Is Regal installed? See https://github.com/StyraInc/regal\n"
                f"{detail}"
            )

    os.makedirs(os.path.dirname(regal_suggestion_path) or ".", exist_ok=True)
    with open(regal_suggestion_path, "w") as file:
        file.write(content)
    return content


if __name__ == "__main__":
    policy_dir = os.getenv("POLICY_DIR")
    regal_suggestion_path = os.getenv("REGAL_SUGGESTION_PATH")
    create_regal_suggestion(policy_dir, regal_suggestion_path)
