# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import glob
import os
import json
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN


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


def read_files(file_path, command_dict):
    commands = []
    with open(file_path, "r") as f:
        lines = f.readlines()
    lines = [line.strip() for line in lines]
    for line in lines:
        with open(line, "r") as file:
            data = json.load(file)
            # Handle both old format (original_command) and new format (agent.input)
            if "original_command" in data.get("input", {}):
                command = data["input"]["original_command"]
            elif "agent" in data.get("input", {}).get("extensions", {}):
                command = data["input"]["extensions"]["agent"]["input"]
            else:
                # Fallback: use the entire input as string
                command = str(data.get("input", {}))
            commands.append(command)
            command_dict[command] = line
    return commands, command_dict


def cluster_commands(cluster_results, test_path, eps=0.3, min_samples=2):
    commands_fp = []
    commands_fn = []
    command_dict = {}
    commands_fp, command_dict = read_files(test_path + "fp.txt", command_dict)
    if len(commands_fp) < 1:
        print("no false positives found...")
    commands_fn, command_dict = read_files(test_path + "fn.txt", command_dict)
    if len(commands_fn) < 1:
        print("no false negatives found...")

    model = SentenceTransformer("all-MiniLM-L6-v2")
    clusters = []
    cluster_dict = {}

    if len(commands_fp) > 0:
        embeddings = model.encode(commands_fp)
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
        labels = clustering.fit_predict(embeddings)
        clusters.append("Benign commands that should be allowed: ")
        for command, label in zip(commands_fp, labels):
            if label not in cluster_dict.keys():
                cluster_dict[label] = []
            cluster_dict[label].append(command)
        for label in sorted(cluster_dict.keys()):
            clusters.append("Cluster " + str(label) + ": ")
            countt = 0
            for cmd in cluster_dict[label]:
                countt = countt + 1
                clusters.append(
                    "Test Case "
                    + str(countt)
                    + ": "
                    + cmd
                    + "\nFile path: "
                    + command_dict[cmd]
                )
            clusters.append("\n")
    base_cluster_id = int(len(cluster_dict.keys()))

    if len(commands_fn) > 0:
        cluster_dict = {}
        embeddings = model.encode(commands_fn)
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
        labels = clustering.fit_predict(embeddings)
        clusters.append("Malicious commands that should not get allowed: ")
        for command, label in zip(commands_fn, labels):
            if label not in cluster_dict.keys():
                cluster_dict[label] = []
            cluster_dict[label].append(command)
        for label in sorted(cluster_dict.keys()):
            countt = 0
            cluster_label = str(int(label) + base_cluster_id)
            clusters.append("Cluster " + str(cluster_label) + ": ")
            for cmd in cluster_dict[label]:
                countt = countt + 1
                clusters.append(
                    "Test Case "
                    + str(countt)
                    + ": "
                    + cmd
                    + "\nFile path: "
                    + command_dict[cmd]
                )
            clusters.append("\n")
    with open(cluster_results, "w", encoding="utf-8") as f:
        f.write("\n".join(clusters))

    return clusters
