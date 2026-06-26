#!/usr/bin/env python3
# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path
from kubectlcmdprocessor.parser import KubectlParser


def extract_commands(file_path):
    commands = []
    file = Path(file_path)

    with open(file, "r") as f:
        for command in f:
            commands.append(command.strip())

    return commands


if __name__ == "__main__":
    directory = "commands"
    commands = extract_commands(directory)

    parser = KubectlParser()

    print("Original commands found:")
    for i, command in enumerate(commands, 1):
        print(f"{i}. {command}")
        with open(f"tests/unlabeled_command{i}.json", "w") as f:
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
