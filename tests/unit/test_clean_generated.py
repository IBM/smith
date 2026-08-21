# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit test for scripts/clean_generated.sh.

Runs the real script against a throwaway ROOT (its optional first arg) so it
never touches the actual skill tree.
"""

import subprocess
from pathlib import Path

import pytest

# repo/skill root = three parents up from tests/unit/this_file
SKILL_ROOT = Path(__file__).resolve().parents[2]
CLEAN_SCRIPT = SKILL_ROOT / "scripts" / "clean_generated.sh"


def _build_root(root: Path):
    (root / "references").mkdir(parents=True)
    (root / "assets").mkdir(parents=True)
    ares = root / "src" / "smith" / "test_generation" / "ares" / "assets"
    ares.mkdir(parents=True)

    # preserved templates
    (root / "references" / "test_case_template.json").write_text("{}")
    (root / "references" / "promptfoo_config_template.yaml").write_text("x: 1\n")
    # generated artifacts (should be removed)
    (root / "references" / "decomp_file.json").write_text("gen")
    (root / "references" / "test_cases").mkdir()
    (root / "references" / "test_cases" / "c0.json").write_text("{}")
    # ares generated (should be removed)
    (ares / "foo_generate.json").write_text("{}")
    (ares / "attack_goals.json").write_text("{}")
    # policy under management (should be emptied, not deleted)
    (root / "assets" / "policy.rego").write_text("package x\nallow = true\n")


@pytest.fixture
def cleaned_root(tmp_path):
    _build_root(tmp_path)
    result = subprocess.run(
        ["bash", str(CLEAN_SCRIPT), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return tmp_path


def test_policy_emptied_but_present(cleaned_root):
    policy = cleaned_root / "assets" / "policy.rego"
    assert policy.exists()
    assert policy.read_text() == ""


def test_templates_preserved(cleaned_root):
    assert (cleaned_root / "references" / "test_case_template.json").exists()
    assert (cleaned_root / "references" / "promptfoo_config_template.yaml").exists()


def test_generated_references_removed(cleaned_root):
    assert not (cleaned_root / "references" / "decomp_file.json").exists()
    assert not (cleaned_root / "references" / "test_cases").exists()


def test_ares_assets_removed(cleaned_root):
    ares = cleaned_root / "src" / "smith" / "test_generation" / "ares" / "assets"
    assert not (ares / "foo_generate.json").exists()
    assert not (ares / "attack_goals.json").exists()
