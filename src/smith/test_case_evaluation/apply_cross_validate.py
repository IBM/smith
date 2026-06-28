# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""
Apply cross-validation results to fix mislabeled test cases.

Reads the cross_validate_report.json, and for each case where the user approved
the suggested action, moves or removes the test case file. Moved files get a
"cv_" prefix to avoid name conflicts with existing cases.

Usage via CLI:
    smith --flag apply_cross_validate
"""

import json
import os
import shutil


def apply_cross_validate_results(report_file, test_case_base_path):
    """
    Read the cross-validation report and apply approved actions.

    Actions:
    - "move_to_allow": move file from disallow/ to allow/ with cv_ prefix
    - "move_to_disallow": move file from allow/ to disallow/ with cv_ prefix
    - "remove": delete the file
    - "keep": do nothing (policy issue, not a mislabel)
    """
    if not os.path.exists(report_file):
        print(f"Report file not found: {report_file}")
        print("Run 'smith --flag cross_validate' first.")
        return

    with open(report_file, "r") as f:
        report = json.load(f)

    cases = report.get("cases", [])
    if not cases:
        print("No cases in the report.")
        return

    allow_dir = os.path.join(test_case_base_path, "allow")
    disallow_dir = os.path.join(test_case_base_path, "disallow")

    moved = 0
    removed = 0
    skipped = 0

    print(f"Applying cross-validation results from: {report_file}")
    print(f"Test case directory: {test_case_base_path}")
    print("=" * 60)

    for case in cases:
        action = case.get("suggested_action", "keep")
        path = case.get("path", "")
        filename = case.get("filename", os.path.basename(path))

        if action == "keep":
            skipped += 1
            continue

        if not os.path.exists(path):
            print(f"  SKIP (not found): {filename}")
            skipped += 1
            continue

        prefixed_name = f"cv_{filename}"

        if action == "move_to_allow":
            dest = os.path.join(allow_dir, prefixed_name)
            shutil.move(path, dest)
            print(f"  MOVED to allow/: {filename} -> {prefixed_name}")
            moved += 1

        elif action == "move_to_disallow":
            dest = os.path.join(disallow_dir, prefixed_name)
            shutil.move(path, dest)
            print(f"  MOVED to disallow/: {filename} -> {prefixed_name}")
            moved += 1

        elif action == "remove":
            os.remove(path)
            print(f"  REMOVED: {filename}")
            removed += 1

        else:
            print(f"  SKIP (unknown action '{action}'): {filename}")
            skipped += 1

    print("=" * 60)
    print(f"Done. Moved: {moved}, Removed: {removed}, Skipped: {skipped}")
