# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
"""Saving the artifacts one pipeline step produced.

`save_snapshot` (the CLI flag) captures a run's final state: the policy, the
guidance, the test cases. This captures what a *single* step generated, so a
run can be archived stage by stage and two runs compared step against step.

Each step owns a set of paths, resolved from the same `.env` values the CLI
assembles them from. The saved layout mirrors the source tree under the
destination (`references/...`, `assets/...`), so a saved step is recognisable
without a key. Missing sources are skipped with a warning: a step that has not
run yet, or whose optional artifacts the `ATTACK_TOOLS` setting never produces,
saves whatever exists rather than failing.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .console import out

#: Step number -> (label, [relative paths]). Paths ending in "/" are copied as
#: trees, everything else as single files. They are relative to the skill root,
#: and resolved against it so the saved layout mirrors the source.
STEP_ARTIFACTS: dict[int, tuple[str, tuple[str, ...]]] = {
    1: ("create OPA policy", (
        "assets/policy.rego",
    )),
    2: ("generate test cases", (
        "references/decomp_file.json",
        "references/decomp_flatten_file.json",
        "references/grey_guidance.json",
        "references/vars_file.json",
        "references/test_cases.json",
        "references/decomp_attack_file.json",
        "references/decomp_attack_file_promptfoo.json",
        "references/decomp_attack_file_promptfoo_classified.json",
        "references/bypass_cases.json",
        "references/bypass/",
        "references/guidance_case_map.json",
        "references/guidance_snapshot.txt",
        "references/guidance_raw_snapshot.txt",
        "references/test_cases/",
    )),
    3: ("translate test cases", (
        "references/test_cases/",
        "references/test_cases/miscalled_cases.json",
    )),
    4: ("policy testing", (
        "assets/policy.rego",
        "references/scorecard/",
    )),
    5: ("cross-validate failed test cases", (
        "references/cross_validate_report.json",
        "references/test_cases/",
    )),
    6: ("patch failed test cases", (
        "assets/policy.rego",
        "assets/opa/outputs/cluster_results.txt",
    )),
    7: ("regal suggestions and fixes", (
        "assets/policy.rego",
        "assets/opa/outputs/regal_suggestion.txt",
    )),
    8: ("duplication suggestions and fixes", (
        "assets/policy.rego",
        "assets/opa/outputs/graph_suggestion.txt",
        "assets/opa/outputs/linting_feedback_de-duplication.json",
        "assets/opa/outputs/linting_feedback_de-duplication.md",
        "assets/opa/ast.json",
        "assets/opa/ast.dot",
    )),
    9: ("enhance guidance with security analysis", ()),
    10: ("introduce policy defects", ()),
}

#: Steps whose artifacts live under the target agent rather than the skill
#: root, so they follow TARGET_AGENT_PATH instead of being fixed paths.
AGENT_ARTIFACTS: dict[int, tuple[str, ...]] = {
    1: ("smith/tool_definitions.json",),
    2: ("smith/promptfooconfig.yaml",),
    9: ("smith/guidance.txt", "smith/guidance_updated.txt",
        "smith/guidelines-security-analysis/"),
    10: ("smith/policy_defect.rego", "smith/defect_summary.txt"),
}


def _copy_file(src: Path, dest: Path, base: Path) -> int:
    if not src.is_file():
        out.say(f"  {out.dim}[skip] {_label(src, base)}{out.off}")
        return 0
    target = dest / _label(src, base)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    out.say(f"  [ok]   {_label(src, base)}")
    return 1


def _copy_tree(src: Path, dest: Path, base: Path) -> int:
    if not src.is_dir():
        out.say(f"  {out.dim}[skip] {_label(src, base)}/{out.off}")
        return 0
    target = dest / _label(src, base)
    count = 0
    for root, _dirs, files in os.walk(src):
        for name in sorted(files):
            source = Path(root) / name
            copied = target / source.relative_to(src)
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, copied)
            count += 1
    out.say(f"  [ok]   {_label(src, base)}/ "
            f"({count} file{'s' if count != 1 else ''})")
    return count


def _label(path: Path, base: Path) -> str:
    """`path` relative to `base`, or its name when it falls outside."""
    try:
        return str(path.relative_to(base))
    except ValueError:
        return path.name


def step_paths(root: Path, step: int, agent: str | None) -> list[Path]:
    """Every artifact path step `step` owns, agent-relative ones included."""
    _label_, relatives = STEP_ARTIFACTS[step]
    paths = [root / rel for rel in relatives]
    if agent:
        agent_root = root / agent
        paths += [agent_root / rel for rel in AGENT_ARTIFACTS.get(step, ())]
    return paths


def save_step(root: Path, step: int, dest: Path,
              agent: str | None = None) -> int:
    if step not in STEP_ARTIFACTS:
        valid = ", ".join(str(n) for n in sorted(STEP_ARTIFACTS))
        raise ValueError(f"unknown step {step} (valid: {valid})")

    label = STEP_ARTIFACTS[step][0]
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    out.info(f"Saving step {step} ({label}) artifacts to {dest}")

    seen: set[Path] = set()
    trees: list[Path] = []
    copied = 0
    # Trees first, so a file already inside one is recognisable as a duplicate.
    paths = step_paths(root, step, agent)
    ordered = sorted(paths, key=lambda p: not (str(p).endswith(os.sep)
                                               or p.is_dir()))
    for src in ordered:
        if src in seen:
            continue
        seen.add(src)
        if str(src).endswith(os.sep) or src.is_dir():
            copied += _copy_tree(src, dest, root)
            trees.append(src.resolve())
            continue
        if any(tree in src.resolve().parents for tree in trees):
            continue
        copied += _copy_file(src, dest, root)

    if copied:
        out.ok(f"Saved {copied} file{'s' if copied != 1 else ''}")
    else:
        out.warn("Nothing saved: none of this step's artifacts exist yet.")
    return copied
