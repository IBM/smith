"""
Validate an OPA policy file by running opa fmt and opa check.

Usage:
    python scripts/policy_generation/validate_policy.py --policy assets/policy_generated.rego
"""

import argparse
import subprocess
import sys
import shutil
from pathlib import Path


def check_opa_installed():
    """Check if opa binary is available."""
    if shutil.which("opa") is None:
        print("ERROR: 'opa' binary not found in PATH.")
        print("Install OPA: https://www.openpolicyagent.org/docs/latest/#1-download-opa")
        return False
    return True


def run_opa_fmt(policy_path: str) -> tuple:
    """Run opa fmt to check syntax and format the policy."""
    try:
        result = subprocess.run(
            ["opa", "fmt", policy_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return False, f"opa fmt failed:\n{result.stderr}"

        with open(policy_path, "r") as f:
            original = f.read()

        if result.stdout and result.stdout != original:
            return True, "Policy has formatting differences (opa fmt would rewrite)"

        return True, "Policy syntax is valid"
    except subprocess.TimeoutExpired:
        return False, "opa fmt timed out"
    except Exception as e:
        return False, f"Error running opa fmt: {e}"


def run_opa_fmt_write(policy_path: str) -> tuple:
    """Run opa fmt -w to format the policy in place."""
    try:
        result = subprocess.run(
            ["opa", "fmt", "-w", policy_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return False, f"opa fmt -w failed:\n{result.stderr}"
        return True, "Policy formatted successfully"
    except subprocess.TimeoutExpired:
        return False, "opa fmt -w timed out"
    except Exception as e:
        return False, f"Error running opa fmt -w: {e}"


def run_opa_check(policy_path: str) -> tuple:
    """Run opa check to validate the policy."""
    try:
        result = subprocess.run(
            ["opa", "check", policy_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return False, f"opa check failed:\n{result.stderr}"
        return True, "Policy passes opa check"
    except subprocess.TimeoutExpired:
        return False, "opa check timed out"
    except Exception as e:
        return False, f"Error running opa check: {e}"


def run_opa_eval_smoke(policy_path: str) -> tuple:
    """Run a basic opa eval to ensure the policy can be loaded."""
    try:
        result = subprocess.run(
            ["opa", "eval", "-d", policy_path, "data.mcp.policies.allow"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return False, f"opa eval smoke test failed:\n{result.stderr}"
        return True, "Policy loads and evaluates successfully"
    except subprocess.TimeoutExpired:
        return False, "opa eval timed out"
    except Exception as e:
        return False, f"Error running opa eval: {e}"


def validate_policy(policy_path: str) -> bool:
    """Validate an OPA policy file (fmt check + opa check + eval smoke). Returns True if all pass."""
    if not Path(policy_path).exists():
        print(f"ERROR: Policy file not found: {policy_path}")
        return False

    if not check_opa_installed():
        return False

    print(f"Validating policy: {policy_path}")
    print("=" * 60)

    all_passed = True

    success, msg = run_opa_fmt(policy_path)
    print(f"[{'PASS' if success else 'FAIL'}] opa fmt: {msg}")
    if not success:
        all_passed = False

    success, msg = run_opa_check(policy_path)
    print(f"[{'PASS' if success else 'FAIL'}] opa check: {msg}")
    if not success:
        all_passed = False

    success, msg = run_opa_eval_smoke(policy_path)
    print(f"[{'PASS' if success else 'FAIL'}] opa eval (smoke): {msg}")
    if not success:
        all_passed = False

    print("=" * 60)
    if all_passed:
        print("All validation checks passed.")
    else:
        print("Some validation checks failed. Fix errors above and re-run.")
    return all_passed


def fix_and_validate_policy(policy_path: str) -> bool:
    """Auto-format and validate an OPA policy file. Returns True if all pass."""
    if not Path(policy_path).exists():
        print(f"ERROR: Policy file not found: {policy_path}")
        return False

    if not check_opa_installed():
        return False

    print(f"Formatting and validating policy: {policy_path}")
    print("=" * 60)

    all_passed = True

    success, msg = run_opa_fmt_write(policy_path)
    print(f"[{'PASS' if success else 'FAIL'}] opa fmt -w: {msg}")
    if not success:
        all_passed = False

    success, msg = run_opa_check(policy_path)
    print(f"[{'PASS' if success else 'FAIL'}] opa check: {msg}")
    if not success:
        all_passed = False

    success, msg = run_opa_eval_smoke(policy_path)
    print(f"[{'PASS' if success else 'FAIL'}] opa eval (smoke): {msg}")
    if not success:
        all_passed = False

    print("=" * 60)
    if all_passed:
        print("All validation checks passed.")
    else:
        print("Some validation checks failed. Fix errors above and re-run.")
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Validate OPA policy")
    parser.add_argument("--policy", required=True, help="Path to the .rego policy file")
    parser.add_argument("--fix", action="store_true", help="Auto-format the policy with opa fmt -w")
    args = parser.parse_args()

    if args.fix:
        success = fix_and_validate_policy(str(args.policy))
    else:
        success = validate_policy(str(args.policy))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
