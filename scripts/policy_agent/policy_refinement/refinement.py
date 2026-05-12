from dotenv import load_dotenv
import os
from pathlib import Path
import re
import json
from policy_agent.reduce_improve.detect_redundancy import write_graph_suggestion


def load_file(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_file(path: Path, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def extract_rule_names_from_feedback_json(json_data, source_name: str):
    rule_names = set()

    issues = json_data.get("issues", [])

    for issue in issues:
        rule = issue.get("rule_name")
        if isinstance(rule, str):
            cleaned = re.split(r"[^\w]", rule)[0]
            rule_names.add(cleaned)

    return {name: source_name for name in rule_names}


def extract_nodes_from_graph(graph_text: str):
    node_pattern = re.compile(r"\['([a-zA-Z0-9_]+)'\]")
    return set(node_pattern.findall(graph_text))


def find_rule_blocks(policy_text: str):
    lines = policy_text.splitlines()
    rule_blocks = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = re.match(r"^([a-zA-Z0-9_]+)\s+if\s*{", line)
        if match:
            rule_name = match.group(1)
            start = i
            brace_depth = 0
            for j in range(i, len(lines)):
                brace_depth += lines[j].count("{")
                brace_depth -= lines[j].count("}")
                if brace_depth == 0 and j > i:
                    end = j
                    break
            else:
                end = i
            rule_blocks.append({
                "rule_name": rule_name,
                "start": start,
                "end": end,
                "body": "\n".join(lines[start:end + 1])
            })
            i = end
        i += 1
    return rule_blocks


def remove_redundant_rules(policy_text: str, target_rule_names):
    rule_blocks = find_rule_blocks(policy_text)
    lines = policy_text.splitlines()
    to_remove = set()

    for block in rule_blocks:
        if block["rule_name"] in target_rule_names:
            for i in range(block["start"], block["end"] + 1):
                to_remove.add(i)

    cleaned_lines = []
    for i, line in enumerate(lines):
        if i not in to_remove:
            cleaned_lines.append(line)
        else:
            if i == min(
                [
                    b["start"]
                    for b in rule_blocks
                    if b["rule_name"] in target_rule_names
                    and b["start"] <= i <= b["end"]
                ],
                default=i,
            ):
                cleaned_lines.append(
                    f"# Removed redundant rule: {block['rule_name']} (from deadrules + graph)"
                )

    return "\n".join(cleaned_lines)


def refactor_policy_with_feedback(policy_path, output_dir, graph_path, graph_suggestion_path, output_path):
    write_graph_suggestion(graph_path, graph_suggestion_path)

    policy_text = load_file(policy_path)

    feedback_files = {
        "de-duplication": Path(output_dir) / "linting_feedback_de-duplication.json",
        "cycle-detection": Path(output_dir) / "linting_feedback_cycle-detection.json",
        "deadrules": Path(output_dir) / "linting_feedback_deadrules.json",
    }


    rules_by_file = {}
    for name, feedback_file in feedback_files.items():
        if feedback_file.exists():
            json_data = load_json(feedback_file)
            rules = extract_rule_names_from_feedback_json(json_data, feedback_file.name)
            rules_by_file[name] = set(rules.keys())
        else:
            rules_by_file[name] = set()

    graph_text = load_file(graph_suggestion_path)
    graph_nodes = extract_nodes_from_graph(graph_text)

    removable_rules = rules_by_file.get("deadrules", set()).intersection(graph_nodes)

    print("Feedback sources:")
    for name, rules in rules_by_file.items():
        print(f"   - {name}: {sorted(rules)}")

    print(f"\nNodes from graph: {sorted(graph_nodes)}")
    print(f"Rules eligible for removal (deadrules ∩ graph nodes): {sorted(removable_rules)}")

    if not removable_rules:
        print("No rules found that exist in both 'deadrules' feedback and graph nodes.")
        return

    new_policy = remove_redundant_rules(policy_text, removable_rules)

    header = (
        "# ==========================================\n"
        "# AUTO-GENERATED REFACTORED POLICY\n"
        "# Based on feedback from multiple analyses + graph nodes\n"
        "# ==========================================\n\n"
    )

    new_policy = header + new_policy

    save_file(output_path, new_policy)
    save_file(policy_path, new_policy)

    print(f"Refactored policy saved to: {output_path}")
    print(f"Rewrite policy to: {policy_path}")
    return str(policy_path)


if __name__ == "__main__":
    load_dotenv()
    base_url = os.getenv("BASE_URL")
    copy_save_dir = os.getenv("COPY_SAVE_DIR")
    policy_path = Path(os.getenv("POLICY_PATH"))
    output_dir = os.path.join(base_url, copy_save_dir, "tmp", "feedback")

    graph_path = Path(os.path.join(base_url, "src", "policy_agent", "reduce_improve", "graph_redundancy.txt"))
    output_path = Path(os.path.join(base_url, "policies", "policy.rego"))

    refactor_policy_with_feedback(policy_path, output_dir, graph_path, output_path)
