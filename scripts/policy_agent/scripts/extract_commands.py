#!/usr/bin/env python3
# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path
from kubectlcmdprocessor.parser import KubectlParser


def extract_original_commands(directory_path):
    commands = []
    json_files = Path(directory_path).glob("*.json")

    for json_file in sorted(json_files):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                original_command = data.get("input", {}).get("original command", "")
                if original_command:
                    commands.append(original_command.strip())
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading {json_file}: {e}")

    return commands


if __name__ == "__main__":
    directory = "tests/integration/inputs/benign_commands"
    commands = extract_original_commands(directory)

    parser = KubectlParser()

    print("Original commands found:")
    for i, command in enumerate(commands, 1):
        print(f"{i}. {command}")
        with open(
            f"tests/integration/new_inputs/benign_commands/processed_command{i}.json",
            "w",
        ) as f:
            f.write(
                json.dumps(
                    {
                        "input": {
                            **parser.parse(command),
                            **{"original_command": command},
                        }
                    },
                    indent=2,
                )
            )

    print(f"\nTotal commands: {len(commands)}")
