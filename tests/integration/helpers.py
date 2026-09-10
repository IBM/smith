# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Shared constants and helpers for the Smith test suite.

One base class, two lanes:

* ``EnvBase`` — the shared behavior: ``get``/``path``/``rel`` path resolution, the
  artifact accessors (``policy``, ``test_cases``, ``scorecard``, …), and
  ``override(**kw)`` for layering environment changes.
* ``SmithEnv(EnvBase)`` — ``__init__`` loads ``.env`` and takes the initial
  environment from it, exactly as the ``smith`` CLI does. Used by ``integration``
  and ``llm`` tests, which exercise each CLI flag's real execution.
* ``UnitEnv(EnvBase)`` — ``__init__`` assigns preset variables directly: no
  ``.env``, no credentials, no external service. Inputs resolve to the frozen
  ``fixtures/`` tree, outputs to ``tmp_path``. Used by ``unit`` tests, which call
  individual functions directly. This is what lets ``make ci`` run the unit subset
  on a bare GitHub runner.

Because dotenv loading lives in ``SmithEnv.__init__`` rather than at module scope,
importing this module reads no configuration — so collecting a unit-only run never
touches a developer's ``.env``.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE_POLICY = FIXTURES / "policy" / "policy.rego"
FIXTURE_TEST_CASES = FIXTURES / "test_cases"
FIXTURE_PROMPTFOO_CONFIG = FIXTURES / "promptfoo" / "promptfooconfig.yaml"

EXPECTED = {
    # confusion counts (allow-allowed=tn, allow-denied=fp,
    # disallow-denied=tp, disallow-allowed=fn)
    "tn": 30,
    "fp": 5,
    "tp": 70,
    "fn": 10,
    # per-experiment summary numbers
    "allow_total": 35,
    "disallow_total": 80,
    # coverage the OPA `opa test --coverage` run reports for this policy
    "coverage": 86.48648648648648,
    "covered_lines": 64,
    "not_covered_lines": 10,
    # `wc -l` of the fixture policy
    "policy_lines": 153,
}


def which(binary: str) -> bool:
    return shutil.which(binary) is not None

class EnvBase:
    """Shared behavior for both lanes: path resolution and env overriding.

    Subclasses differ only in where ``self.env`` and ``self.base`` come from:
    ``SmithEnv`` loads ``.env``; ``UnitEnv`` assigns preset values.
    """

    base: str
    env: dict

    # -- overriding -------------------------------------------------------
    def override(self, **overrides) -> dict:
        env = dict(self.env)
        for key, value in overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = str(value)
        return env

    # -- resolution -------------------------------------------------------
    def get(self, var: str, default: str | None = None) -> str:
        value = self.env.get(var, default)
        if value is None:
            raise KeyError(
                f"{var} is not set; tests resolve artifact paths from the same "
                "variables the smith CLI uses."
            )
        return value

    def _base_for(self, var: str) -> str:
        return self.base

    def path(self, *vars_: str, default: str | None = None) -> Path:
        """Resolve ``base + env[var] + ...`` as a ``Path``."""
        parts = [
            self.get(v, default if i == len(vars_) - 1 else None)
            for i, v in enumerate(vars_)
        ]
        return Path(self._base_for(vars_[0]) + "".join(parts))

    def rel(self, path, is_dir: bool | None = None) -> str:
        """Express ``path`` the way an .env value does: relative to ``base``."""
        target = Path(path).resolve()
        base = Path(self.base).resolve()
        try:
            rel = target.relative_to(base).as_posix()
        except ValueError:
            raise ValueError(
                f"{target} is not under {base}, so it cannot be expressed as an "
                ".env value."
            ) from None
        if is_dir is None:
            is_dir = str(path).endswith(("/", os.sep)) or target.is_dir()
        if rel and is_dir:
            rel += "/"
        return rel

    # -- common artifacts -------------------------------------------------
    @property
    def policy(self) -> Path:
        return self.path("POLICY_DIR", "POLICY_PATH")

    @property
    def test_cases(self) -> Path:
        return self.path("TEST_CASE_PATH")

    @property
    def references(self) -> Path:
        return Path(self.base) / "references"

    @property
    def scorecard(self) -> Path:
        return self.path("TEST_OUTPUT_DIR")

    @property
    def scorecard_summary(self) -> Path:
        return self.path("TEST_OUTPUT_DIR", "TEST_RESULT_PATH")

    @property
    def failures_file(self) -> Path:
        return self.path("TEST_OUTPUT_DIR", "TEST_FAILURES_PATH")

    @property
    def guidance_file(self) -> Path:
        return self.path("GUIDANCE_FILE")

    @property
    def system_var_file(self) -> Path:
        return self.path("SYSTEM_VAR_FILE")

    @property
    def case_template(self) -> Path:
        return self.path("TEST_CASE_TEMPLATE")

    @property
    def generation_artifacts(self) -> dict:
        """The intermediates the ``test_generation`` pipeline writes."""
        return {
            "decomp": self.path("DECOMP_FILE"),
            "flatten": self.path("FLATTEN_FILE"),
            "vars": self.path("VARS_FILE"),
            "grey": self.path("GREY_GUIDANCE_FILE"),
            "cases": self.path("CASE_FILE"),
            "promptfoo_attack": self.path("ATTACK_FILE_PROMPT"),
        }

    @property
    def bypass_report_dir(self) -> Path:
        return self.path("BYPASS_REPORT_DIR")

    @property
    def bypass_cases_file(self) -> Path:
        return self.path("BYPASS_CASE_FILE")

    @property
    def cross_validate_output(self) -> Path:
        return self.path("CROSS_VALIDATE_OUTPUT")


class SmithEnv(EnvBase):
    """The **real** Smith environment — integration"""

    def __init__(self, env: dict | None = None, base: str | None = None):
        if env is None:
            load_dotenv()
            source = dict(os.environ)
        else:
            source = dict(env)
        self.env = {k: v for k, v in source.items() if v}
        self.base = base or self.env.get("BASE_URL")

    @property
    def example(self) -> Path:
        """The call-for-papers example target agent (a real checkout path)."""
        return Path(self.base) / "examples" / "call-for-papers-mcp"

    def missing(self, *vars_: str) -> list:
        """Which of ``vars_`` are unset — for the gating fixtures' skip reasons."""
        return [v for v in vars_ if not self.env.get(v)]


class UnitEnv(EnvBase):
    """A faked environment for the unit lane — **no ``.env``, no credentials**."""

    INPUTS = {
        "POLICY_DIR": "policy/",
        "POLICY_PATH": "policy.rego",
        "TEST_CASE_PATH": "test_cases/",
        "TEST_CASE_TEMPLATE": "test_case_template.json",
        "GUIDANCE_FILE": "guidance.txt",
        "SYSTEM_VAR_FILE": "system_vars.json",
    }

    #: Output vars, resolved under the writable temp root. Mirrors .env's layout
    #: so the code under test sees the paths it expects.
    OUTPUTS = {
        "BASE_URL": None,  # filled in per instance
        "DATA_DIR": "assets/opa/",
        "FINAL_TEST_CASES": "references/test_cases/",
        "TEST_OUTPUT_DIR": "references/scorecard/",
        "TEST_RESULT_PATH": "scorecard_summary.txt",
        "TEST_FAILURES_PATH": "score_test_failures.txt",
        "SESSION_CONFIG_FILE": "references/session_config.json",
        "DECOMP_FILE": "references/decomp_file.json",
        "FLATTEN_FILE": "references/decomp_flatten_file.json",
        "VARS_FILE": "references/vars_file.json",
        "GREY_GUIDANCE_FILE": "references/grey_guidance.json",
        "CASE_FILE": "references/test_cases.json",
        "ATTACK_FILE_PROMPT": "references/decomp_attack_file_promptfoo.json",
        "CROSS_VALIDATE_OUTPUT": "references/cross_validate_report.json",
        "BYPASS_REPORT_DIR": "references/bypass/",
        "BYPASS_CASE_FILE": "references/bypass_cases.json",
    }

    def __init__(self, tmp_root: Path, fixtures: Path = FIXTURES):
        self.root = Path(tmp_root)
        # Smith concatenates BASE_URL with relative paths, so the trailing
        # separator is part of the value's contract.
        self.base = str(fixtures) + os.sep # for input, BASE_URL for output. 
        self.out_base = str(self.root) + os.sep
        outputs = {k: v for k, v in self.OUTPUTS.items() if v is not None}
        self.env = {**self.INPUTS, **outputs, "BASE_URL": self.out_base}
        for sub in ("assets", "references", "assets/opa/outputs"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def _base_for(self, var: str) -> str:
        """Outputs go to the temp root; inputs come from the fixture tree."""
        return self.base if var in self.INPUTS else self.out_base

    # -- authoring extra inputs (always temp-rooted) ----------------------
    def write(self, rel_path: str, content: str) -> Path:
        p = self.root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return p

    def write_json(self, rel_path: str, payload) -> Path:
        return self.write(rel_path, json.dumps(payload, indent=2))

    def copy_test_cases(self) -> Path:
        """Copy the frozen case set into the temp root, for a mutating test.

        Use this when the code under test moves or deletes case files (e.g.
        translation routing, apply_cross_validate) — the fixture tree itself must
        stay pristine.
        """
        dst = self.root / "references" / "test_cases"
        if dst.exists():
            shutil.rmtree(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(FIXTURE_TEST_CASES, dst)
        return dst


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len([ln for ln in path.read_text().splitlines() if ln.strip()])


def load_json(path: Path):
    return json.loads(Path(path).read_text())


def parse_scorecard_summary(text: str) -> dict:
    """Parse ``scorecard_summary.txt`` into a structured dict.

    Returns::

        {
          "experiments": [
            {"experiment": <title>, "directory": <dir>,
             "allowed": int, "denied": int, "total": int},
            ...
          ],
          "coverage": float | None,
          "policy_lines": int | None,
        }

    Mirrors the block format written by ``src/smith/policy_testing/score_card.sh``.
    """
    experiments = []
    current: dict = {}
    coverage = None
    covered_lines = None
    not_covered_lines = None
    policy_lines = None
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        line = raw.strip()
        if line.startswith("Experiment:"):
            current = {"experiment": line.split(":", 1)[1].strip()}
        elif line.startswith("Directory:"):
            current["directory"] = line.split(":", 1)[1].strip()
        elif line.startswith("Allowed:"):
            current["allowed"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("Denied:"):
            current["denied"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("Total:"):
            current["total"] = int(line.split(":", 1)[1].strip())
            experiments.append(current)
            current = {}
        elif '"covered_lines":' in line:
            covered_lines = int(line.split(":", 1)[1].strip().rstrip(","))
        elif '"not_covered_lines":' in line:
            not_covered_lines = int(line.split(":", 1)[1].strip().rstrip(","))
        elif '"coverage":' in line:
            coverage = float(line.split(":", 1)[1].strip().rstrip(","))
        elif line.startswith("The line number of current policy is:"):
            # The count is on the following non-empty line.
            for nxt in lines[i + 1 :]:
                if nxt.strip():
                    policy_lines = int(nxt.strip())
                    break
    return {
        "experiments": experiments,
        "coverage": coverage,
        "covered_lines": covered_lines,
        "not_covered_lines": not_covered_lines,
        "policy_lines": policy_lines,
    }
