# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import glob
import os
import json
import pickle


def find_files_recursively(root_dir, pattern):
    search_path = os.path.join(root_dir, "**", pattern)
    matching_files = glob.glob(search_path, recursive=True)
    return matching_files


def read_records_command(file_path="agent_analytics_sdk_logs*"):
    files = find_files_recursively("./trace/", file_path)
    command_line_all = []
    for f in files:
        with open(f, "r") as file:
            contents = file.read()
            objects = contents.strip().split("\n}\n{")
            objects[0] += "}"
            for i in range(1, len(objects) - 1):
                objects[i] = "{" + objects[i] + "}"
            objects[-1] = "{" + objects[-1]
            command_indexes = []
            record = {}
            for obj in objects:
                data = json.loads(obj)
                if data["name"] == "chat.completions.create":
                    for data_key in data["attributes"].keys():
                        if ("gen_ai.prompt") in data_key or (
                            "gen_ai.completion" in data_key
                        ):
                            if ("content" in data_key) and data[
                                "parent_id"
                            ] + "_" + data_key not in record.keys():
                                record[data["parent_id"] + "_" + data_key] = data[
                                    "attributes"
                                ][data_key]
                if data["name"] == "NL2Kubectl Tool.tool":
                    if data["status"]["status_code"] == "ERROR":
                        continue
                    record[
                        data["context"]["span_id"] + "_" + "traceloop.entity.input"
                    ] = data["attributes"]["traceloop.entity.input"]
                    command_indexes.append(data["context"]["span_id"])
            command_line = record[
                command_indexes[-1] + "_" + "gen_ai.completion.0.content"
            ]
            command_line = process_command_format(command_line)
            command_line_all.append(command_line)
    return command_line_all


def process_command_format(command):
    if len(command.split("\n")) == 3:
        return command.split("\n")[1]
    return ""


def save_file(data, filename):
    with open(filename, "wb") as handle:
        pickle.dump(data, handle)


command_line_all = read_records_command()
print(command_line_all)
save_file(command_line_all, "extracted_cases.pkl")
