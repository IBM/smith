#!/usr/bin/env python3
"""
OPA Policy Coverage Analyzer

This tool analyzes test coverage for OPA policies by:
1. Reading coverage data from tests/integration/coverage.txt
2. Mapping covered line ranges to rule names in the revised_policy.rego
3. Comparing with the main policy.rego to identify covered and uncovered rules

Usage:
    python tools/coverage_analyzer.py
"""

import json
import re
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass


@dataclass
class CoverageRange:
    """Represents a coverage range with start and end line numbers"""

    start_line: int
    end_line: int


@dataclass
class RuleInfo:
    """Information about a policy rule"""

    name: str
    line_number: int
    rule_type: str
    end_line: int = None


@dataclass
class CoverageAnalysis:
    """Results of coverage analysis"""

    covered_rules: List[RuleInfo]
    uncovered_rules: List[RuleInfo]
    coverage_percentage: float
    total_rules: int


class PolicyCoverageAnalyzer:
    """Analyzes OPA policy test coverage"""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()
        self.coverage_file = (
            self.project_root / "tests" / "integration" / "coverage.txt"
        )
        self.revised_policy_file = (
            self.project_root
            / "tests"
            / "integration"
            / "coverage"
            / "revised_policy.rego"
        )
        self.main_policy_file = self.project_root / "policies" / "policy.rego"

    def load_coverage_data(self) -> Dict:
        """Load and parse coverage data from coverage.txt"""
        try:
            with open(self.coverage_file, "r") as f:
                coverage_data = json.load(f)
            return coverage_data
        except FileNotFoundError:
            raise FileNotFoundError(f"Coverage file not found: {self.coverage_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in coverage file: {e}")

    def extract_covered_ranges(self, coverage_data: Dict) -> List[CoverageRange]:
        """Extract covered line ranges for revised_policy.rego"""
        revised_policy_key = None

        files_data = coverage_data.get("files", {})
        for file_path in files_data.keys():
            if "revised_policy.rego" in file_path:
                revised_policy_key = file_path
                break

        if not revised_policy_key:
            raise ValueError("revised_policy.rego not found in coverage data")

        file_coverage = files_data[revised_policy_key]
        covered_ranges = []

        for range_data in file_coverage.get("covered", []):
            start_line = range_data["start"]["row"]
            end_line = range_data["end"]["row"]
            covered_ranges.append(CoverageRange(start_line, end_line))

        return covered_ranges

    def extract_rules_from_policy(self, policy_file: Path) -> List[RuleInfo]:
        """Extract all rule definitions from a policy file"""
        rules = []

        try:
            with open(policy_file, "r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            raise FileNotFoundError(f"Policy file not found: {policy_file}")

        for line_num, line in enumerate(lines, 1):
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            rule_match = self._match_rule_definition(line)
            if rule_match:
                rule_name, rule_type = rule_match
                end_line = self._find_rule_end_line(lines, line_num - 1, rule_type)
                rules.append(RuleInfo(rule_name, line_num, rule_type, end_line))

        return rules

    def _match_rule_definition(self, line: str) -> Optional[Tuple[str, str]]:
        """Match and extract rule name and type from a line"""

        patterns = [
            (r"^([a-zA-Z_][a-zA-Z0-9_]*)\s+if\s*{", "rule"),
            (r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:=", "assignment"),
            (r"^default\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*:=", "default"),
            (r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*=", "assignment"),
        ]

        for pattern, rule_type in patterns:
            match = re.match(pattern, line)
            if match:
                return match.group(1), rule_type

        return None

    def _find_rule_end_line(
        self, lines: List[str], start_index: int, rule_type: str
    ) -> int:
        """Find the end line number for a rule"""
        start_line = start_index + 1

        if rule_type in ["assignment", "default"]:

            brace_count = 0
            bracket_count = 0
            paren_count = 0
            in_string = False

            for i in range(start_index, len(lines)):
                line = lines[i].strip()

                for char_idx, char in enumerate(line):
                    if char == '"' and (char_idx == 0 or line[char_idx - 1] != "\\"):
                        in_string = not in_string
                    elif not in_string:
                        if char == "{":
                            brace_count += 1
                        elif char == "}":
                            brace_count -= 1
                        elif char == "[":
                            bracket_count += 1
                        elif char == "]":
                            bracket_count -= 1
                        elif char == "(":
                            paren_count += 1
                        elif char == ")":
                            paren_count -= 1

                if brace_count == 0 and bracket_count == 0 and paren_count == 0:
                    return i + 1

                if i - start_index > 20:
                    break

            return start_line

        elif rule_type == "rule":
            brace_count = 0
            found_opening = False

            for i in range(start_index, len(lines)):
                line = lines[i].strip()

                for char in line:
                    if char == "{":
                        brace_count += 1
                        found_opening = True
                    elif char == "}":
                        brace_count -= 1
                        if found_opening and brace_count == 0:
                            return i + 1

                if i - start_index > 50:
                    break

            return start_line

        return start_line

    def is_line_covered(
        self, line_number: int, covered_ranges: List[CoverageRange]
    ) -> bool:
        """Check if a line number is covered by any coverage range"""
        for coverage_range in covered_ranges:
            if coverage_range.start_line <= line_number <= coverage_range.end_line:
                return True
        return False

    def analyze_coverage(self) -> CoverageAnalysis:
        """Perform complete coverage analysis"""

        coverage_data = self.load_coverage_data()
        covered_ranges = self.extract_covered_ranges(coverage_data)

        revised_rules = self.extract_rules_from_policy(self.revised_policy_file)

        covered_rules = []
        uncovered_rules = []

        for rule in revised_rules:
            if self.is_line_covered(rule.line_number, covered_ranges):
                covered_rules.append(rule)
            else:
                uncovered_rules.append(rule)

        total_rules = len(revised_rules)
        coverage_percentage = (
            (len(covered_rules) / total_rules * 100) if total_rules > 0 else 0
        )

        return CoverageAnalysis(
            covered_rules=covered_rules,
            uncovered_rules=uncovered_rules,
            coverage_percentage=coverage_percentage,
            total_rules=total_rules,
        )

    def compare_with_main_policy(self) -> Dict[str, Set[str]]:
        """Compare rules between main policy and revised policy"""
        main_rules = self.extract_rules_from_policy(self.main_policy_file)
        revised_rules = self.extract_rules_from_policy(self.revised_policy_file)

        main_rule_names = {rule.name for rule in main_rules}
        revised_rule_names = {rule.name for rule in revised_rules}

        return {
            "common_rules": main_rule_names & revised_rule_names,
            "main_only": main_rule_names - revised_rule_names,
            "revised_only": revised_rule_names - main_rule_names,
        }

    def generate_report(
        self, analysis: CoverageAnalysis, output_format: str = "text"
    ) -> str:
        """Generate a coverage report"""
        if output_format == "json":
            return self._generate_json_report(analysis)
        else:
            return self._generate_text_report(analysis)

    def _generate_json_report(self, analysis: CoverageAnalysis) -> str:
        """Generate JSON format report"""
        report_data = {
            "summary": {
                "total_rules": analysis.total_rules,
                "covered_rules_count": len(analysis.covered_rules),
                "uncovered_rules_count": len(analysis.uncovered_rules),
                "coverage_percentage": round(analysis.coverage_percentage, 2),
            },
            "covered_rules": [
                {
                    "name": rule.name,
                    "start_line": rule.line_number,
                    "end_line": rule.end_line,
                    "type": rule.rule_type,
                }
                for rule in analysis.covered_rules
            ],
            "uncovered_rules": [
                {
                    "name": rule.name,
                    "start_line": rule.line_number,
                    "end_line": rule.end_line,
                    "type": rule.rule_type,
                }
                for rule in analysis.uncovered_rules
            ],
        }

        return json.dumps(report_data, indent=2)

    def _generate_text_report(self, analysis: CoverageAnalysis) -> str:
        """Generate text format report"""
        report_lines = [
            "=" * 60,
            "OPA POLICY COVERAGE ANALYSIS REPORT",
            "=" * 60,
            "",
            f"Total Rules: {analysis.total_rules}",
            f"Covered Rules: {len(analysis.covered_rules)}",
            f"Uncovered Rules: {len(analysis.uncovered_rules)}",
            f"Coverage Percentage: {analysis.coverage_percentage:.2f}%",
            "",
            "COVERED RULES:",
            "-" * 40,
        ]

        if analysis.covered_rules:
            for rule in sorted(analysis.covered_rules, key=lambda r: r.line_number):
                line_range = (
                    f"{rule.line_number}-{rule.end_line}"
                    if rule.end_line and rule.end_line != rule.line_number
                    else str(rule.line_number)
                )
                report_lines.append(
                    f" {rule.name} (lines {line_range}, {rule.rule_type})"
                )
        else:
            report_lines.append("No rules are covered by tests.")

        report_lines.extend(["", "UNCOVERED RULES:", "-" * 40])

        if analysis.uncovered_rules:
            for rule in sorted(analysis.uncovered_rules, key=lambda r: r.line_number):
                line_range = (
                    f"{rule.line_number}-{rule.end_line}"
                    if rule.end_line and rule.end_line != rule.line_number
                    else str(rule.line_number)
                )
                report_lines.append(
                    f" {rule.name} (lines {line_range}, {rule.rule_type})"
                )
        else:
            report_lines.append("All rules are covered by tests!")

        try:
            comparison = self.compare_with_main_policy()
            report_lines.extend(
                [
                    "",
                    "POLICY COMPARISON:",
                    "-" * 40,
                    f"Rules in both policies: {len(comparison['common_rules'])}",
                    f"Rules only in main policy: {len(comparison['main_only'])}",
                    f"Rules only in revised policy: {len(comparison['revised_only'])}",
                ]
            )

            if comparison["main_only"]:
                report_lines.extend(
                    [
                        "",
                        "Rules only in main policy:",
                        ", ".join(sorted(comparison["main_only"])),
                    ]
                )

            if comparison["revised_only"]:
                report_lines.extend(
                    [
                        "",
                        "Rules only in revised policy:",
                        ", ".join(sorted(comparison["revised_only"])),
                    ]
                )
        except Exception as e:
            report_lines.extend(["", f"Policy comparison failed: {e}"])

        report_lines.append("=" * 60)

        return "\n".join(report_lines)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Analyze OPA policy test coverage")
    parser.add_argument(
        "--output-format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory)",
    )

    args = parser.parse_args()

    try:
        analyzer = PolicyCoverageAnalyzer(args.project_root)
        analysis = analyzer.analyze_coverage()
        report = analyzer.generate_report(analysis, args.output_format)
        print(report)

        if analysis.coverage_percentage < 100:
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
