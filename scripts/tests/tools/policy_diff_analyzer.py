#!/usr/bin/env python3

import json
import difflib
import argparse
import sys
import re
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# ANSI color codes
ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"


@dataclass
class PolicyDiffResult:
    """Results of policy diff analysis"""

    old_policy_path: str
    new_policy_path: str
    added_rules: List[str]
    modified_rules: List[str]
    removed_rules: List[str]
    rule_stats: Dict[str, Tuple[int, int, List[str]]]
    package_changed: Optional[Tuple[str, str]]
    imports_added: set
    imports_removed: set
    total_inserted: int
    total_deleted: int


class PolicyDiffAnalyzer:
    """Analyzes differences between OPA policy files"""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()
        self.baseline_policy = self.project_root / "policies" / "policy.rego"

    def find_newest_policy(self, search_dirs: List[str] = None) -> Optional[Path]:
        if search_dirs is None:
            repair_dir = os.getenv("REPAIR_DIR", "")
            mutation_dir = os.getenv("MUTATION_DIR", "")
            search_dirs = [d for d in (repair_dir, mutation_dir) if d]

        if not search_dirs:
            print(
                "Error: No search directories specified. Set REPAIR_DIR and/or MUTATION_DIR environment variables.",
                file=sys.stderr,
            )
            return None

        newest_file = None
        newest_time = 0
        searched_paths = []

        for search_dir in search_dirs:
            dir_path = self.project_root / "resources" / "data" / search_dir
            searched_paths.append(str(dir_path))

            if not dir_path.exists():
                print(f"Warning: Directory does not exist: {dir_path}", file=sys.stderr)
                continue

            found_files = []
            for rego_file in dir_path.rglob("*.rego"):
                if any(skip in str(rego_file) for skip in ["test", "backup", "_old"]):
                    continue

                found_files.append(str(rego_file))
                mtime = rego_file.stat().st_mtime
                if mtime > newest_time:
                    newest_time = mtime
                    newest_file = rego_file

            if found_files:
                print(
                    f"Found {len(found_files)} policy files in {dir_path}",
                    file=sys.stderr,
                )

        if newest_file is None:
            print(
                "Error: No new policy files found in repair/defective directories",
                file=sys.stderr,
            )
            print(f"Searched paths: {searched_paths}", file=sys.stderr)

        return newest_file

    def extract_rules(self, file_path: Path) -> Dict[str, List[str]]:
        """Extract rules from a Rego policy file"""
        if not file_path.exists():
            raise FileNotFoundError(f"Policy file not found: {file_path}")

        rules = {}
        current_rule = None
        nesting_level = 0

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if nesting_level == 0:

                if (
                    stripped.endswith("{")
                    and ":=" not in stripped
                    and not stripped.startswith('"')
                ):
                    rule_name = stripped.split()[0]
                    current_rule = rule_name
                    rules[current_rule] = [line.rstrip()]
                    nesting_level += 1
                    continue

                if ":=" in stripped and stripped.endswith("{"):
                    rule_name = stripped.split(":=")[0].strip()
                    current_rule = rule_name
                    rules[current_rule] = [line.rstrip()]
                    nesting_level += 1
                    continue

                if ":=" in stripped and not stripped.endswith("{"):
                    rule_name = stripped.split(":=")[0].strip()
                    rules[rule_name] = [line.rstrip()]
                    continue

            if current_rule:
                rules[current_rule].append(line.rstrip())

            nesting_level += line.count("{")
            nesting_level -= line.count("}")

            if current_rule and nesting_level == 0:
                current_rule = None

        return rules

    def extract_package_imports(self, file_path: Path) -> Tuple[Optional[str], set]:
        """Extract package and import statements"""
        package = None
        imports = set()

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("#") or not stripped:
                    continue
                if stripped.startswith("package "):
                    package = stripped
                elif stripped.startswith("import "):
                    imports.add(stripped)

        return package, imports

    def diff_rule_lines(
        self, old_lines: List[str], new_lines: List[str]
    ) -> Tuple[int, int, List[str]]:
        """Calculate diff statistics for rule lines"""
        diff = list(difflib.ndiff(old_lines, new_lines))
        inserted = sum(1 for d in diff if d.startswith("+ "))
        deleted = sum(1 for d in diff if d.startswith("- "))
        return inserted, deleted, diff

    def analyze_policies(self, old_policy: Path, new_policy: Path) -> PolicyDiffResult:
        """Perform comprehensive diff analysis between two policies"""

        old_rules = self.extract_rules(old_policy)
        new_rules = self.extract_rules(new_policy)

        all_rule_names = set(old_rules.keys()).union(new_rules.keys())

        added_rules = [r for r in new_rules if r not in old_rules]
        removed_rules = [r for r in old_rules if r not in new_rules]
        modified_rules = []

        rule_stats = {}
        for rule in sorted(all_rule_names):
            old_lines = old_rules.get(rule, [])
            new_lines = new_rules.get(rule, [])
            inserted, deleted, diff = self.diff_rule_lines(old_lines, new_lines)

            if inserted > 0 or deleted > 0:
                if rule not in added_rules and rule not in removed_rules:
                    modified_rules.append(rule)

            rule_stats[rule] = (inserted, deleted, diff)

        old_package, old_imports = self.extract_package_imports(old_policy)
        new_package, new_imports = self.extract_package_imports(new_policy)

        package_changed = None
        if old_package != new_package:
            package_changed = (old_package, new_package)

        imports_added = new_imports - old_imports
        imports_removed = old_imports - new_imports

        total_inserted = sum(ins for ins, del_, _ in rule_stats.values())
        total_deleted = sum(del_ for ins, del_, _ in rule_stats.values())

        return PolicyDiffResult(
            old_policy_path=str(old_policy),
            new_policy_path=str(new_policy),
            added_rules=added_rules,
            modified_rules=modified_rules,
            removed_rules=removed_rules,
            rule_stats=rule_stats,
            package_changed=package_changed,
            imports_added=imports_added,
            imports_removed=imports_removed,
            total_inserted=total_inserted,
            total_deleted=total_deleted,
        )

    def generate_text_report(self, result: PolicyDiffResult) -> str:
        """Generate human-readable text report"""
        lines = []

        lines.extend(
            [
                "=" * 60,
                "OPA POLICY DIFF ANALYSIS REPORT",
                "=" * 60,
                "",
                f"Baseline Policy: {result.old_policy_path}",
                f"Compared Policy: {result.new_policy_path}",
                f"Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
            ]
        )

        total_rules = len(result.rule_stats)
        lines.extend(
            [
                "SUMMARY:",
                f"Total Rules: {total_rules}",
                f"Added Rules: {len(result.added_rules)}",
                f"Modified Rules: {len(result.modified_rules)}",
                f"Removed Rules: {len(result.removed_rules)}",
                f"Total Lines Inserted: {result.total_inserted}",
                f"Total Lines Deleted: {result.total_deleted}",
                "",
            ]
        )

        if result.rule_stats:
            rule_name_width = max(len(rule) for rule in result.rule_stats) + 2
            count_width = 10

            header = f"{'Rule':<{rule_name_width}}{'Inserted':>{count_width}}{'Deleted':>{count_width}}{'Status'}"
            lines.extend(
                [
                    "RULE MODIFICATIONS:",
                    header,
                    "-" * (rule_name_width + 2 * count_width + 10),
                ]
            )

            for rule, (inserted, deleted, _) in sorted(result.rule_stats.items()):
                if rule in result.added_rules:
                    status = f"{GREEN}ADDED{RESET}"
                elif rule in result.removed_rules:
                    status = f"{RED}REMOVED{RESET}"
                elif rule in result.modified_rules:
                    status = f"{YELLOW}MODIFIED{RESET}"
                else:
                    status = "UNCHANGED"

                lines.append(
                    f"{rule:<{rule_name_width}}{inserted:>{count_width}}{deleted:>{count_width}} {status}"
                )

            lines.append("-" * (rule_name_width + 2 * count_width + 10))

        if result.package_changed:
            lines.extend(
                [
                    "",
                    f"{YELLOW}PACKAGE MODIFIED:{RESET}",
                    f"Old: {result.package_changed[0]}",
                    f"New: {result.package_changed[1]}",
                ]
            )

        if result.imports_added:
            lines.extend(["", f"{GREEN}IMPORTS ADDED:{RESET}"])
            for imp in result.imports_added:
                lines.append(f"  {imp}")

        if result.imports_removed:
            lines.extend(["", f"{RED}IMPORTS REMOVED:{RESET}"])
            for imp in result.imports_removed:
                lines.append(f"  {imp}")

        if result.modified_rules or result.added_rules or result.removed_rules:
            lines.extend(["", "CHANGED RULES SUMMARY:", "-" * 40])

            if result.added_rules:
                lines.extend(
                    ["", f"{GREEN}ADDED RULES ({len(result.added_rules)}):{RESET}"]
                )
                for rule in sorted(result.added_rules):
                    inserted, _, _ = result.rule_stats[rule]
                    lines.append(f"  + {rule} ({inserted} lines)")

            if result.modified_rules:
                lines.extend(
                    [
                        "",
                        f"{YELLOW}MODIFIED RULES ({len(result.modified_rules)}):{RESET}",
                    ]
                )
                for rule in sorted(result.modified_rules):
                    inserted, deleted, _ = result.rule_stats[rule]
                    lines.append(f"  ~ {rule} (+{inserted}/-{deleted} lines)")

            if result.removed_rules:
                lines.extend(
                    ["", f"{RED}REMOVED RULES ({len(result.removed_rules)}):{RESET}"]
                )
                for rule in sorted(result.removed_rules):
                    deleted, _, _ = result.rule_stats[rule]
                    lines.append(f"  - {rule} ({deleted} lines)")

        lines.append("=" * 60)
        return "\n".join(lines)

    def generate_json_report(self, result: PolicyDiffResult) -> str:
        """Generate JSON report"""
        report_data = {
            "analysis_info": {
                "baseline_policy": result.old_policy_path,
                "compared_policy": result.new_policy_path,
                "analysis_time": datetime.now().isoformat(),
            },
            "summary": {
                "total_rules": len(result.rule_stats),
                "added_rules_count": len(result.added_rules),
                "modified_rules_count": len(result.modified_rules),
                "removed_rules_count": len(result.removed_rules),
                "total_lines_inserted": result.total_inserted,
                "total_lines_deleted": result.total_deleted,
            },
            "rule_changes": {
                "added_rules": result.added_rules,
                "modified_rules": result.modified_rules,
                "removed_rules": result.removed_rules,
            },
            "rule_statistics": {
                rule: {"inserted": ins, "deleted": del_}
                for rule, (ins, del_, _) in result.rule_stats.items()
            },
            "package_changes": {
                "package_modified": result.package_changed is not None,
                "old_package": (
                    result.package_changed[0] if result.package_changed else None
                ),
                "new_package": (
                    result.package_changed[1] if result.package_changed else None
                ),
            },
            "import_changes": {
                "imports_added": list(result.imports_added),
                "imports_removed": list(result.imports_removed),
            },
        }

        return json.dumps(report_data, indent=2)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Analyze differences between OPA policy files"
    )
    parser.add_argument(
        "--new-policy",
        type=Path,
        help="Path to the new policy file (auto-detected if not specified)",
    )
    parser.add_argument(
        "--baseline-policy",
        type=Path,
        default=Path("policies/policy.rego"),
        help="Path to the baseline policy file (default: policies/policy.rego)",
    )
    parser.add_argument(
        "--output-format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help="Output file path (default: resources/data/outputs/policy_diff_output.txt for text, policy_diff_output.json for JSON)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory)",
    )

    args = parser.parse_args()

    try:
        analyzer = PolicyDiffAnalyzer(args.project_root)

        baseline_policy = args.project_root / args.baseline_policy
        if not baseline_policy.exists():
            print(
                f"Error: Baseline policy not found: {baseline_policy}", file=sys.stderr
            )
            sys.exit(1)

        if args.new_policy:
            new_policy = args.project_root / args.new_policy
            if not new_policy.exists():
                print(
                    f"Error: Specified new policy not found: {new_policy}",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            new_policy = analyzer.find_newest_policy()
            if not new_policy:
                print(
                    "Error: No new policy files found in repair/defective directories",
                    file=sys.stderr,
                )
                sys.exit(1)
            print(f"Auto-detected newest policy: {new_policy}")

        result = analyzer.analyze_policies(baseline_policy, new_policy)

        if args.output_format == "json":
            report = analyzer.generate_json_report(result)
            default_output = (
                args.project_root
                / "resources"
                / "data"
                / "outputs"
                / "policy_diff_output.json"
            )
        else:
            report = analyzer.generate_text_report(result)
            default_output = (
                args.project_root
                / "resources"
                / "data"
                / "outputs"
                / "policy_diff_output.txt"
            )

        output_file = args.output_file or default_output

        output_file.parent.mkdir(parents=True, exist_ok=True)

        clean_report = ANSI_ESCAPE.sub("", report)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(clean_report)

        print(report)
        print(f"\nOutput written to: {output_file}")

        if result.total_inserted > 0 or result.total_deleted > 0:
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
