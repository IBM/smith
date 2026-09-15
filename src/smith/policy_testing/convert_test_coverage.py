# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Generate an OPA coverage test file from the scorecard's tp/tn case lists.

Invoked argument-less by ``score_card.sh``; it resolves its paths from the
environment (``BASE_URL``, ``POLICY_DIR``, ``POLICY_PATH``, and
``SMITH_SCORECARD_DIR`` / ``TEST_OUTPUT_DIR``) and writes two files that ``opa
test --coverage`` then reads:

    <out_dir>/coverage/revised_policy.rego   the policy, with its own test_*
                                             rules renamed out of the way
    <out_dir>/coverage/policy_test.rego      one rego test per scored case

Environment resolution and file writing happen in ``main()``, not at import, so
the transformation helpers below can be imported and tested on their own.
"""

import json
import re
import os
from dotenv import load_dotenv


def replace_quotes_in_json(obj, old_char="'", new_char='"'):
    if "command" not in obj.keys():
        return obj
    for k in obj["command"].keys():
        if isinstance(obj["command"][k], str):
            obj["command"][k] = obj["command"][k].replace(old_char, new_char)
        elif isinstance(obj["command"][k], list):
            for k_index in range(len(obj["command"][k])):
                if isinstance(obj["command"][k][k_index], str):
                    obj["command"][k][k_index] = obj["command"][k][k_index].replace(
                        old_char, new_char
                    )
                elif isinstance(obj["command"][k][k_index], dict):
                    for kk in obj["command"][k][k_index].keys():
                        if isinstance(obj["command"][k][k_index][kk], str):
                            obj["command"][k][k_index][kk] = obj["command"][k][k_index][
                                kk
                            ].replace(old_char, new_char)
                        else:
                            obj["command"][k][k_index][kk] = "null"
                else:
                    obj["command"][k][k_index] = "null"

        else:
            obj["command"][k] = "null"
    obj["original_command"] = obj["original_command"].replace(old_char, new_char)

    return str(obj)


def fix_package_line(file_path, new_package="policy"):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = r"(?m)^package\s+[a-zA-Z0-9_.]+"
    new_content = re.sub(pattern, f"package {new_package}", content, count=1)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"[OK] Updated package in {file_path}")


def collect_test_functions(content):
    pattern = r"(?m)^\s*(test_[A-Za-z0-9_]*)\s*(\(|\{|=|if\b)"
    names = set()
    for m in re.finditer(pattern, content):
        name = m.group(1)
        names.add(name)
    return sorted(names)


def build_rename_map(names, new_prefix="_test_"):
    rename_map = {}
    for name in names:
        suffix = name[len("test_") :]
        new_name = f"{new_prefix}{suffix}"
        rename_map[name] = new_name
    return rename_map


def apply_renames(content, rename_map):
    for old, new in rename_map.items():
        pattern = r"\b" + re.escape(old) + r"\b"
        content = re.sub(pattern, new, content)
    return content


def process_file(policy_path, file_path, new_prefix="_test_"):
    with open(policy_path, "r", encoding="utf-8") as f:
        content = f.read()
    names = collect_test_functions(content)
    if not names:
        print(f"[INFO] No test_* functions found in {file_path}")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return

    print(f"[INFO] Found in {file_path}:")
    for n in names:
        print(f"   - {n}")

    rename_map = build_rename_map(names, new_prefix=new_prefix)

    print("[INFO] Rename map:")
    for old, new in rename_map.items():
        print(f"   {old}  ->  {new}")
    new_content = apply_renames(content, rename_map)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[OK] Updated {file_path}\n")


def read_files(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()
    lines = [line.strip() for line in lines]
    return lines


def try_parse_rego_json(content):
    """Validate that content is parseable as JSON. If not, return None."""
    try:
        json.loads(content)
        return content
    except (json.JSONDecodeError, ValueError):
        return None


def render_case_input(case_input):
    """Render a case's ``input`` object as the rego literal used in a test body.

    The stringified-dict form is preferred because it keeps the original key
    order, but it is only used when it round-trips as valid JSON; otherwise the
    output falls back to ``json.dumps``.
    """
    content = str(replace_quotes_in_json(case_input))
    content = content.replace('"', '\\"')
    content = content.replace("'", '"')
    content = content.replace('"null"', "null")
    if try_parse_rego_json(content) is None:
        content = json.dumps(case_input, ensure_ascii=False)
    return content


def build_test_rules(case_paths, rule_prefix, assertion):
    """Build one rego test rule per case file, numbered from 1.

    ``assertion`` is the body line's operator text — ``"policy.allow"`` for cases
    the policy should allow, ``"not policy.allow"`` for cases it should deny.
    """
    rules = []
    for index, case_file in enumerate(case_paths, start=1):
        with open(case_file, "r") as f:
            data = json.load(f)
        rules.append(
            "\n".join(
                [
                    f"{rule_prefix}{index} if {{",
                    f"    {assertion} with input as {render_case_input(data['input'])}",
                    "}",
                ]
            )
        )
    return rules


def build_coverage_tests(
    policy_path,
    revised_policy_path,
    test_file_path,
    tp_command_path,
    tn_command_path,
):
    """Rewrite the policy for coverage and emit the rego test file.

    Every path is explicit — no environment lookups, no module-level state — so
    this is callable from a test with temporary files. Returns the test file's
    text as well as writing it.
    """
    process_file(policy_path, revised_policy_path)
    fix_package_line(revised_policy_path)

    # Local, not module-level: accumulating across calls would emit duplicate
    # test rules and produce a rego file that does not compile.
    final_results = ["package policy_test", "import data.policy"]
    final_results += build_test_rules(
        read_files(tp_command_path), "test_not_allow_", "not policy.allow"
    )
    final_results += build_test_rules(
        read_files(tn_command_path), "test_allow_", "policy.allow"
    )

    text = "\n\n".join(final_results)
    with open(test_file_path, "w") as f:
        f.write(text)
    return text


def main():
    """Resolve paths from the environment and generate the coverage tests.

    ``score_card.sh`` invokes this module as a script with no arguments, so the
    environment is the interface: it must keep reading the same variables and
    writing the same two filenames.
    """
    load_dotenv()

    base_url = os.getenv("BASE_URL")
    policy_dir = base_url + os.getenv("POLICY_DIR")
    policy_path = policy_dir + os.getenv("POLICY_PATH")
    # Scorecard outputs live under the skill root (set by score_card.sh), never in
    # the installed package directory.
    out_dir = os.getenv("SMITH_SCORECARD_DIR") or os.path.join(
        base_url, os.getenv("TEST_OUTPUT_DIR", "references/scorecard/")
    )
    out_dir = os.path.join(out_dir, "")  # ensure a trailing separator
    os.makedirs(os.path.join(out_dir, "coverage"), exist_ok=True)

    build_coverage_tests(
        policy_path=policy_path,
        revised_policy_path=out_dir + "coverage/revised_policy.rego",
        test_file_path=out_dir + "coverage/policy_test.rego",
        tp_command_path=out_dir + "tp.txt",
        tn_command_path=out_dir + "tn.txt",
    )


if __name__ == "__main__":
    main()
