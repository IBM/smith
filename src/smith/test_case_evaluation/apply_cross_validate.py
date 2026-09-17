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

from smith.test_generation import guidance_map


def apply_cross_validate_results(
    report_file, test_case_base_path, guidance_map_file=None
):
    """
    Read the cross-validation report and apply approved actions.

    Actions:
    - "move_to_allow": move file from disallow/ to allow/ with cv_ prefix
    - "move_to_disallow": move file from allow/ to disallow/ with cv_ prefix
    - "remove": delete the file
    - "keep": do nothing (policy issue, not a mislabel)

    Every move and removal is reported to the guidance map when
    ``guidance_map_file`` is given, so the guidance -> test-case relation keeps
    pointing at files that actually exist.
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
    # Case-tree-relative old path -> new path, or None when deleted. Handed to the
    # guidance map afterwards so it keeps pointing at files that exist.
    moves = {}

    def _relative(absolute):
        return os.path.relpath(absolute, test_case_base_path).replace(os.sep, "/")

    def _free_destination(directory, name):
        # if the file exists, should warn and add suffixes
        candidate = os.path.join(directory, name)
        if not os.path.exists(candidate):
            return candidate
        stem, extension = os.path.splitext(name)
        suffix = 2
        while os.path.exists(os.path.join(directory, f"{stem}_{suffix}{extension}")):
            suffix += 1
        resolved = os.path.join(directory, f"{stem}_{suffix}{extension}")
        print(
            f"  WARNING: {name} already exists in {os.path.basename(directory)}/; "
            f"writing {os.path.basename(resolved)} instead so the existing case "
            "is not overwritten."
        )
        return resolved

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
            # Create the destination bucket on demand: shutil.move raises
            # FileNotFoundError if it does not already exist, which happens on a
            # fresh case tree or one whose allow/ cases have all been moved out.
            os.makedirs(allow_dir, exist_ok=True)
            dest = _free_destination(allow_dir, prefixed_name)
            shutil.move(path, dest)
            moves[_relative(path)] = _relative(dest)
            print(f"  MOVED to allow/: {filename} -> {os.path.basename(dest)}")
            moved += 1

        elif action == "move_to_disallow":
            os.makedirs(disallow_dir, exist_ok=True)
            dest = _free_destination(disallow_dir, prefixed_name)
            shutil.move(path, dest)
            moves[_relative(path)] = _relative(dest)
            print(f"  MOVED to disallow/: {filename} -> {os.path.basename(dest)}")
            moved += 1

        elif action == "remove":
            moves[_relative(path)] = None
            os.remove(path)
            print(f"  REMOVED: {filename}")
            removed += 1

        else:
            print(f"  SKIP (unknown action '{action}'): {filename}")
            skipped += 1

    if guidance_map_file and moves:
        guidance_map.relocate_cases(guidance_map_file, moves)

    print("=" * 60)
    print(f"Done. Moved: {moved}, Removed: {removed}, Skipped: {skipped}")
