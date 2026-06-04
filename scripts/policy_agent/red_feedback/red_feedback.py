import glob
import os
import json
import pickle
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
from openai import OpenAI
import httpx 
from dotenv import load_dotenv
import re
import sys
load_dotenv()

def find_files_recursively(root_dir, pattern):
    search_path = os.path.join(root_dir, '**', pattern)
    matching_files = glob.glob(search_path, recursive=True)
    return matching_files

def read_records_command(file_path="agent_analytics_sdk_logs*"):
    files = find_files_recursively("./trace/", file_path)
    command_line_all=[]
    for f in files:
        with open(f, 'r') as file:
            contents = file.read()
            objects=contents.strip().split('\n}\n{')
            objects[0] += "}"
            for i in range(1, len(objects) - 1):
                objects[i] = '{' + objects[i] + '}'
            objects[-1] = '{'+ objects[-1]
            command_indexes=[]
            record={}
            for obj in objects:
                data = json.loads(obj) 
                if data['name']=="chat.completions.create":
                    for data_key in data['attributes'].keys():
                        if ("gen_ai.prompt") in data_key or ("gen_ai.completion" in data_key):
                            if ("content" in data_key) and data['parent_id']+"_"+data_key not in record.keys():
                                record[data['parent_id']+"_"+data_key]=data['attributes'][data_key]
                if data['name']=="NL2Kubectl Tool.tool":
                    if data['status']['status_code']=="ERROR":
                        continue
                    record[data['context']['span_id']+"_"+"traceloop.entity.input"]=data['attributes']["traceloop.entity.input"]
                    command_indexes.append(data['context']['span_id'])
            command_line = record[command_indexes[-1]+"_"+"gen_ai.completion.0.content"]
            command_line=process_command_format(command_line)
            command_line_all.append(command_line)
    return command_line_all


def process_command_format(command):
    if len(command.split("\n"))==3:
        return command.split("\n")[1]
    return ''

def save_file(data, filename):
    with open(filename, 'wb') as handle:
        pickle.dump(data, handle)

def read_files(file_path, command_dict):
    commands=[]
    with open(file_path, 'r') as f:
        lines=f.readlines()
    lines=[line.strip() for line in lines]
    for line in lines:
        with open(line, 'r') as file:
            data = json.load(file)
            # Handle both old format (original_command) and new format (agent.input)
            if 'original_command' in data.get('input', {}):
                command = data['input']['original_command']
            elif 'agent' in data.get('input', {}).get('extensions', {}):
                command = data['input']['extensions']['agent']['input']
            else:
                # Fallback: use the entire input as string
                command = str(data.get('input', {}))
            commands.append(command)
            command_dict[command]=line
    return commands, command_dict

def cluster_commands(malicious_commands, cluster_results, test_path):
    commands_fp=[]
    commands_fn=[]
    command_dict={}
    commands_fp, command_dict=read_files(test_path+'fp.txt', command_dict)
    if len(commands_fp)<1:
        print("no false positives found...")
    commands_fn, command_dict=read_files(test_path+'fn.txt', command_dict)
    if len(commands_fn)<1:
        print("no false negatives found...")
            
    model = SentenceTransformer("all-MiniLM-L6-v2")
    clusters=[]
    cluster_dict={}

    if len(commands_fp)>0:
        embeddings = model.encode(commands_fp)
        clustering = DBSCAN(eps=1.8, min_samples=2, metric='cosine')
        labels = clustering.fit_predict(embeddings)
        clusters.append("Benign commands that should be allowed: ")
        for command, label in zip(commands_fp, labels):
            if label not in cluster_dict.keys():
                cluster_dict[label]=[]
            cluster_dict[label].append(command)
        for label in sorted(cluster_dict.keys()):
            clusters.append("Cluster "+str(label)+": ")
            countt=0
            for cmd in cluster_dict[label]:
                countt=countt+1
                clusters.append("Test Case "+str(countt)+": "+cmd + "\nFile path: "+command_dict[cmd])
            clusters.append("\n")
    base_cluster_id=int(len(cluster_dict.keys()))
    
    if len(commands_fn)>0:
        cluster_dict={}
        embeddings = model.encode(commands_fn)
        clustering = DBSCAN(eps=1.8, min_samples=2, metric='cosine')
        labels = clustering.fit_predict(embeddings)
        clusters.append("Malicious commands that should not get allowed: ")
        for command, label in zip(commands_fn, labels):
            if label not in cluster_dict.keys():
                cluster_dict[label]=[]
            cluster_dict[label].append(command)
        for label in sorted(cluster_dict.keys()):
            countt=0
            cluster_label=str(int(label)+base_cluster_id)
            clusters.append("Cluster "+str(cluster_label)+": ")
            for cmd in cluster_dict[label]:
                countt=countt+1
                clusters.append("Test Case "+str(countt)+": "+cmd + "\nFile path: "+command_dict[cmd])
            clusters.append("\n")
    with open(cluster_results, "w", encoding="utf-8") as f:
        f.write("\n".join(clusters))
        
    return clusters

def parse_bracket_clusters(text: str):
    clusters = {}
    current_cluster = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^\[Cluster\s*([-\d]+)\]\s*(.*)$", line)
        if match:
            cluster_id = int(match.group(1))
            cmd = match.group(2).strip()
            clusters.setdefault(cluster_id, []).append(cmd)
            current_cluster = cluster_id
        elif current_cluster is not None:
            clusters[current_cluster].append(line)
        else:
            clusters.setdefault(-1, []).append(line)
    return clusters


def format_clusters_for_prompt(clusters: dict) -> str:
    text_parts = []
    for cid in sorted(clusters.keys()):
        text_parts.append(f"Cluster {cid}\n{'-' * 40}")
        for cmd in clusters[cid]:
            text_parts.append(cmd)
        text_parts.append("")
    return "\n".join(text_parts).strip()
    

def extract_rego_block(text: str):
    match = re.search(r"```(?:rego)?\s*(.*?)```", text, re.S | re.I)
    if match:
        return match.group(1).strip()

    match2 = re.search(r"(package\s+[\s\S]+)$", text, re.I)
    if match2:
        return match2.group(1).strip()

    return None
    
def red_feedback_update(api_key, openai_base_url, cluster_results, malicious_commands, policy_path, red_feedback_analysis_result, modified_policy_red, MODEL, test_path, temp, top_p):

    cluster_commands(malicious_commands, cluster_results, test_path)
    
    http_client = httpx.Client(
        verify=False,    
        timeout=300.0      
    )


    client = OpenAI(
        api_key=api_key,
        base_url=openai_base_url,
        http_client=http_client,
    )

    if not os.path.exists(malicious_commands):
        raise FileNotFoundError(f" Missing {malicious_commands}")
    if not os.path.exists(policy_path):
        raise FileNotFoundError(f"Missing {policy_path}")

    with open(malicious_commands, "r", encoding="utf-8") as f:
        raw_commands = f.read()

    with open(policy_path, "r", encoding="utf-8") as f:
        rego_policy = f.read()


    clusters = parse_bracket_clusters(raw_commands)
    clusters_text = format_clusters_for_prompt(clusters)
    
    if not clusters_text:
        raise ValueError("No clusters found in cluster_command.txt")

    system_instruction = """
    You are a code assistant specialized in analyzing Open Policy Agent (OPA) Rego policies.

    You are given:
    1. A set of clustered kubectl commands that have been identified as potential OPA bypass attempts.
    2. The full Rego policy source code governing kubectl operations.

    # Task
    Analyze the policy and commands to:
    - Identify how each cluster of commands can bypass or evade the policy.
    - Apply minimal and localized edits to strengthen the policy.
    - Modify existing rules where possible instead of adding new ones.
    - Ensure legitimate kubectl usage is not over-restricted.

    # Constraints
    - Do NOT rewrite or refactor the entire policy.
    - Keep rule names, structure, and logic consistent.
    - Add only narrowly scoped conditions to block the bypasses.
    - Maintain the existing allow/deny semantics and namespace checks.

    # Output Format
    1. A detailed analysis section for each cluster.
    2. At the end, include the **complete modified Rego policy** in this format:

    ```rego
    <updated policy here>
    """

    user_prompt = f"""
    Clustered kubectl Commands
    {clusters_text}
    Current Rego Policy
    {rego_policy}
    Instructions
    Analyze how each cluster can bypass the current policy and return the updated Rego code that fixes these bypasses.
    """

    print("Analyzing and strengthening the OPA policy...")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=30000,
        temperature=temp, 
        top_p=top_p
    )


    assistant_output = response.choices[0].message.content


    with open(red_feedback_analysis_result, "w", encoding="utf-8") as f:
        f.write(assistant_output)
    print(f"Full analysis saved to: {red_feedback_analysis_result}")


    rego_block = extract_rego_block(assistant_output)

    if rego_block:
        with open(modified_policy_red, "w", encoding="utf-8") as f:
            f.write(rego_block)
        print(f"Modified Rego policy saved to: {modified_policy_red}")

        with open(policy_path, "w", encoding="utf-8") as f:
            f.write(rego_block)
        print("Policy rewrite")
        
    else:
        print("No Rego code block detected — please check analysis_notes.txt manually.")

    print("Done.")
