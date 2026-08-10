# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Save a flat snapshot of the key Smith artifacts to a destination directory.

Copies, when present:
  - the policy under management        (POLICY_DIR + POLICY_PATH) -> policy.rego
  - the guidance                       (GUIDANCE_FILE)            -> guidance.txt
  - the MCP tool definitions           (TARGET_AGENT_PATH/smith/tool_definitions.json)
  - the promptfoo redteam config       (PROMPTFOO_CONFIG_FILE)
  - the translated test cases          (TEST_CASE_PATH/{allow,disallow}) -> test_cases/{allow,disallow}

Layout is flat: files land directly in ``dest`` (test cases under
``dest/test_cases/{allow,disallow}/``). Missing sources are skipped with a
warning; the snapshot still succeeds with whatever exists.
"""

import os
import shutil


def _copy_file(src, dst_dir, dst_name=None):
    """Copy one file into dst_dir. Returns the basename copied, or None if missing."""
    if not src or not os.path.isfile(src):
        print(f"  [skip] not found: {src}")
        return None
    os.makedirs(dst_dir, exist_ok=True)
    name = dst_name or os.path.basename(src)
    shutil.copy2(src, os.path.join(dst_dir, name))
    print(f"  [ok]   {name}")
    return name


def _copy_case_dir(src_dir, dst_dir, label):
    """Copy the JSON test cases from one bucket (allow/disallow) into dst_dir.

    Returns the number of files copied.
    """
    if not src_dir or not os.path.isdir(src_dir):
        print(f"  [skip] no {label} test cases: {src_dir}")
        return 0
    os.makedirs(dst_dir, exist_ok=True)
    count = 0
    for entry in sorted(os.listdir(src_dir)):
        src = os.path.join(src_dir, entry)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst_dir, entry))
            count += 1
    print(f"  [ok]   test_cases/{label}/ ({count} file{'s' if count != 1 else ''})")
    return count


def save_snapshot(dest, paths):
    """Copy the artifacts named in ``paths`` into ``dest`` (flat layout).

    ``paths`` is a dict with keys: ``policy``, ``guidance``, ``tool_definitions``,
    ``promptfoo_config``, ``test_case_path``. Any value may be missing on disk;
    it is skipped with a warning.
    """
    dest = os.path.abspath(dest)
    os.makedirs(dest, exist_ok=True)
    print(f"Saving Smith snapshot to: {dest}")

    _copy_file(paths.get("policy"), dest, "policy.rego")
    _copy_file(paths.get("guidance"), dest, "guidance.txt")
    _copy_file(paths.get("tool_definitions"), dest, "tool_definitions.json")
    _copy_file(paths.get("promptfoo_config"), dest)

    test_case_path = paths.get("test_case_path")
    if test_case_path:
        _copy_case_dir(
            os.path.join(test_case_path, "allow"),
            os.path.join(dest, "test_cases", "allow"),
            "allow",
        )
        _copy_case_dir(
            os.path.join(test_case_path, "disallow"),
            os.path.join(dest, "test_cases", "disallow"),
            "disallow",
        )
    else:
        print("  [skip] no test_case_path configured")

    print("Snapshot complete.")
    return dest
