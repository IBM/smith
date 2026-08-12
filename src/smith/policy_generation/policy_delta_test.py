"""
Policy Delta Test
=================

Evaluates a Rego policy against labelled test cases and reports pass rate,
fail rate, and the delta vs a previous run.  Use this to track how much a
policy improves (or regresses) after each manual or automated change.

Test-case labels (ground truth)
  /allow/ in path → expected ALLOW
  /deny/  in path → expected DENY

Workflow
--------
  # First measurement — save as baseline
  python policy_delta_test.py policy.rego -t tests/ --json run1.json

  # After policy is changed, measure the delta
  python policy_delta_test.py policy.rego -t tests/ \\
      --previous run1.json --json run2.json

  # Keep running until 95 % pass rate is reached
  python policy_delta_test.py policy.rego -t tests/ \\
      --previous run1.json --target 0.95

Pre-condition
-------------
An OPA server must be running with the policy loaded:
    opa run --server --addr :8181 policy.rego
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass, asdict
from typing import List, Optional


# ===========================================================================
#  1.  Minimal OPA HTTP helpers  (no external deps)
# ===========================================================================

def _opa_get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def _opa_post(url: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _infer_query_url(opa_url: str) -> str:
    """Infer the /v1/data/<pkg>/allow URL from the loaded policy's package."""
    try:
        meta = _opa_get(f"{opa_url}/v1/policies")
        policies = meta.get("result", [])
        if policies:
            raw = _opa_get(
                f"{opa_url}/v1/policies/{policies[0]['id']}"
            ).get("result", {}).get("raw", "")
            for line in raw.split("\n"):
                s = line.strip()
                if s.startswith("package "):
                    pkg = s[len("package "):].strip()
                    return f"{opa_url}/v1/data/{pkg.replace('.', '/')}/allow"
    except Exception:
        pass
    return f"{opa_url}/v1/data/allow"


def _query(query_url: str, input_doc: dict) -> bool:
    try:
        r = _opa_post(query_url, {"input": input_doc})
        return bool(r.get("result", False))
    except Exception:
        return False


# ===========================================================================
#  2.  Test case loader
# ===========================================================================

@dataclass
class TestCase:
    path: str
    input: dict
    expected: bool   # ground-truth label from path convention


def load_test_cases(test_cases_dir: str) -> List[TestCase]:
    """Walk test_cases_dir for *.json files; label by /allow/ or /deny/ in path."""
    if not os.path.isdir(test_cases_dir):
        raise FileNotFoundError(f"test-cases directory not found: {test_cases_dir}")

    cases: List[TestCase] = []
    unlabelled: List[str] = []

    for root, _, files in os.walk(test_cases_dir):
        for fname in sorted(files):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(root, fname)
            with open(fpath) as fh:
                payload = json.load(fh)
            input_doc = (
                payload["input"]
                if isinstance(payload, dict) and "input" in payload
                else payload
            )
            norm = fpath.replace(os.sep, "/")
            if "/allow/" in norm:
                cases.append(TestCase(fpath, input_doc, True))
            elif "/deny/" in norm:
                cases.append(TestCase(fpath, input_doc, False))
            else:
                unlabelled.append(fpath)

    if unlabelled:
        print(f"  warning: {len(unlabelled)} test file(s) have no /allow/ or /deny/ in path — skipped")
    if not cases:
        raise ValueError(f"no labelled test cases found in {test_cases_dir}")
    return cases


# ===========================================================================
#  3.  Evaluation
# ===========================================================================

@dataclass
class CaseResult:
    path: str
    expected: bool
    actual: bool

    @property
    def passed(self) -> bool:
        return self.actual == self.expected


@dataclass
class RunSummary:
    n_total: int
    n_passed: int
    n_failed: int
    pass_rate: float
    fail_rate: float
    failed_cases: List[str]   # paths of failing test cases


def evaluate(query_url: str, cases: List[TestCase]) -> RunSummary:
    results: List[CaseResult] = []
    for tc in cases:
        actual = _query(query_url, tc.input)
        results.append(CaseResult(tc.path, tc.expected, actual))

    n_total  = len(results)
    n_passed = sum(r.passed for r in results)
    n_failed = n_total - n_passed

    return RunSummary(
        n_total=n_total,
        n_passed=n_passed,
        n_failed=n_failed,
        pass_rate=n_passed / n_total if n_total else 0.0,
        fail_rate=n_failed / n_total if n_total else 0.0,
        failed_cases=[r.path for r in results if not r.passed],
    )


# ===========================================================================
#  4.  CLI runner
# ===========================================================================

# ===========================================================================
#  5.  Policy code diff helpers
# ===========================================================================

_RULE_HEADER = re.compile(r'^(deny\[|allow\b|default\s+allow|[a-z_]+\s*:=|[a-z_]+\s+if\s*\{)')


def _read_policy(path: str) -> str:
    try:
        with open(path) as fh:
            return fh.read()
    except OSError:
        return ""


def _diff_policy(old: str, new: str, policy_path: str) -> dict:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff_lines = list(difflib.unified_diff(old_lines, new_lines, fromfile="previous", tofile=policy_path, lineterm=""))

    added   = [l[1:].rstrip() for l in diff_lines if l.startswith("+") and not l.startswith("+++")]
    removed = [l[1:].rstrip() for l in diff_lines if l.startswith("-") and not l.startswith("---")]

    changed_rules: List[str] = []
    for line in added + removed:
        if _RULE_HEADER.match(line.lstrip()):
            name = line.strip().split("{")[0].strip()
            if name not in changed_rules:
                changed_rules.append(name)

    return {
        "lines_added": len(added),
        "lines_removed": len(removed),
        "changed_rules": changed_rules,
        "unified_diff": "".join(diff_lines),
    }


def run(
    policy_path: str,
    test_cases_dir: str,
    opa_url: str,
    target: Optional[float],
    previous_path: Optional[str],
    json_out: Optional[str],
    verbose: bool,
) -> None:
    opa_url = opa_url.rstrip("/")

    print(f"Connecting to OPA at {opa_url} ...")
    query_url = _infer_query_url(opa_url)
    print(f"  query url  : {query_url}")

    print(f"Loading test cases from {test_cases_dir} ...")
    cases = load_test_cases(test_cases_dir)
    n_allow = sum(tc.expected for tc in cases)
    n_deny  = len(cases) - n_allow
    print(f"  test cases : {len(cases)}  (allow={n_allow}, deny={n_deny})")

    print(f"\nEvaluating {policy_path} ...")
    summary = evaluate(query_url, cases)
    policy_text = _read_policy(policy_path)

    # load previous run for delta
    prev: Optional[dict] = None
    if previous_path:
        with open(previous_path) as fh:
            prev = json.load(fh)

    # compute policy code diff if previous run stored the policy text
    code_diff: Optional[dict] = None
    if prev is not None and prev.get("policy_text"):
        code_diff = _diff_policy(prev["policy_text"], policy_text, policy_path)

    # print results
    print()
    print("=" * 50)
    print(f"  Total cases  : {summary.n_total}")
    print(f"  Passed       : {summary.n_passed}  ({summary.pass_rate:.1%})")
    print(f"  Failed       : {summary.n_failed}  ({summary.fail_rate:.1%})")

    if prev is not None:
        prev_pass = prev.get("pass_rate", 0.0)
        delta = summary.pass_rate - prev_pass
        sign  = "+" if delta >= 0 else ""
        print(f"  Delta        : {sign}{delta:.1%}  (prev {prev_pass:.1%} → now {summary.pass_rate:.1%})")

    if target is not None:
        reached = summary.pass_rate >= target
        print(f"  Target       : {target:.1%}  {'✓ REACHED' if reached else '✗ NOT YET'}")

    if code_diff is not None:
        print(f"  Policy lines : +{code_diff['lines_added']} / -{code_diff['lines_removed']}")
        if code_diff["changed_rules"]:
            print(f"  Changed rules: {', '.join(code_diff['changed_rules'])}")
        else:
            print(f"  Changed rules: (none detected)")

    print("=" * 50)

    if code_diff is not None and code_diff["unified_diff"]:
        print("\nPolicy diff:")
        print(code_diff["unified_diff"])

    if summary.n_failed > 0:
        print(f"\nFailed test cases ({summary.n_failed}):")
        for path in summary.failed_cases:
            label = "(expected allow)" if any(
                tc.path == path and tc.expected for tc in cases
            ) else "(expected deny)"
            print(f"  {label}  {path}")

    if verbose and summary.n_passed > 0:
        passed_paths = [r for r in cases if r.path not in summary.failed_cases]
        print(f"\nPassed test cases ({summary.n_passed}):")
        for tc in passed_paths:
            label = "(allow)" if tc.expected else "(deny)"
            print(f"  {label}  {tc.path}")

    if json_out:
        payload = {
            "policy": policy_path,
            "policy_text": policy_text,
            "test_cases_dir": test_cases_dir,
            "n_total": summary.n_total,
            "n_passed": summary.n_passed,
            "n_failed": summary.n_failed,
            "pass_rate": summary.pass_rate,
            "fail_rate": summary.fail_rate,
            "failed_cases": summary.failed_cases,
        }
        if prev is not None:
            payload["delta"] = summary.pass_rate - prev.get("pass_rate", 0.0)
            payload["previous"] = previous_path
        if code_diff is not None:
            payload["policy_diff"] = code_diff
        if target is not None:
            payload["target"] = target
            payload["target_reached"] = summary.pass_rate >= target
        with open(json_out, "w") as fh:
            json.dump(payload, fh, indent=2)
        print(f"\nResults saved to {json_out}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Measure Rego policy pass/fail rate and delta vs a previous run"
    )
    p.add_argument("policy",
                   help="path to the .rego policy (used for display / labelling only)")
    p.add_argument("-t", "--test-cases", dest="test_cases_dir", required=True,
                   help="directory of JSON test cases (recursive, /allow/ and /deny/ paths)")
    p.add_argument("--opa-url", default=os.getenv("SMITH_OPA_URL", "http://localhost:8181"),
                   help="OPA server base URL (default $SMITH_OPA_URL or http://localhost:8181)")
    p.add_argument("--target", type=float, default=None,
                   help="target pass rate 0.0–1.0 (optional; shown in output)")
    p.add_argument("--previous", default=None, dest="previous_path",
                   help="JSON output from a previous run; used to compute delta")
    p.add_argument("--json", dest="json_out", default=None,
                   help="save this run's results to JSON (pass as --previous next time)")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="also list passing test cases")
    args = p.parse_args()

    run(
        args.policy,
        args.test_cases_dir,
        args.opa_url,
        target=args.target,
        previous_path=args.previous_path,
        json_out=args.json_out,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
