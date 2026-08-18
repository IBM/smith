# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for tools.save_snapshot — flat artifact snapshot with skip-and-warn."""

from smith.tools.save_snapshot import save_snapshot


def _make_source(tmp_path):
    """Build a source tree with all artifacts present; return the paths dict."""
    (tmp_path / "policy.rego").write_text("package x\n", encoding="utf-8")
    (tmp_path / "guidance.txt").write_text("rule 1\n", encoding="utf-8")
    (tmp_path / "tool_definitions.json").write_text('{"tools": []}', encoding="utf-8")
    (tmp_path / "promptfooconfig.yaml").write_text("targets: []\n", encoding="utf-8")
    tc = tmp_path / "test_cases"
    (tc / "allow").mkdir(parents=True)
    (tc / "disallow").mkdir(parents=True)
    (tc / "allow" / "a0.json").write_text("{}", encoding="utf-8")
    (tc / "allow" / "a1.json").write_text("{}", encoding="utf-8")
    (tc / "disallow" / "d0.json").write_text("{}", encoding="utf-8")
    return {
        "policy": str(tmp_path / "policy.rego"),
        "guidance": str(tmp_path / "guidance.txt"),
        "tool_definitions": str(tmp_path / "tool_definitions.json"),
        "promptfoo_config": str(tmp_path / "promptfooconfig.yaml"),
        "test_case_path": str(tc),
    }


def test_full_snapshot_flat_layout(tmp_path):
    paths = _make_source(tmp_path)
    dest = tmp_path / "snap"
    save_snapshot(str(dest), paths)

    # renamed top-level artifacts land flat in dest/
    assert (dest / "policy.rego").read_text() == "package x\n"
    assert (dest / "guidance.txt").read_text() == "rule 1\n"
    assert (dest / "tool_definitions.json").exists()
    # promptfoo config keeps its original basename
    assert (dest / "promptfooconfig.yaml").exists()
    # test cases nested under test_cases/{allow,disallow}/
    assert {p.name for p in (dest / "test_cases" / "allow").iterdir()} == {
        "a0.json",
        "a1.json",
    }
    assert {p.name for p in (dest / "test_cases" / "disallow").iterdir()} == {"d0.json"}


def test_missing_artifacts_are_skipped(tmp_path, capsys):
    dest = tmp_path / "snap"
    save_snapshot(
        str(dest),
        {
            "policy": str(tmp_path / "nope.rego"),
            "guidance": None,
            "tool_definitions": None,
            "promptfoo_config": None,
            "test_case_path": str(tmp_path / "nope_tc"),
        },
    )
    # nothing copied, dest still created, no crash
    assert dest.is_dir()
    assert list(dest.iterdir()) == []
    out = capsys.readouterr().out
    assert "[skip]" in out


def test_partial_snapshot(tmp_path):
    paths = _make_source(tmp_path)
    paths["policy"] = str(tmp_path / "missing.rego")  # drop just the policy
    dest = tmp_path / "snap"
    save_snapshot(str(dest), paths)
    assert not (dest / "policy.rego").exists()
    assert (dest / "guidance.txt").exists()
    assert (dest / "test_cases" / "allow" / "a0.json").exists()


def test_empty_test_case_bucket_creates_dir(tmp_path):
    paths = _make_source(tmp_path)
    # remove disallow contents but keep the dir
    for f in (tmp_path / "test_cases" / "disallow").iterdir():
        f.unlink()
    dest = tmp_path / "snap"
    save_snapshot(str(dest), paths)
    # empty bucket still produces an (empty) dir
    assert (dest / "test_cases" / "disallow").is_dir()
    assert list((dest / "test_cases" / "disallow").iterdir()) == []


def test_no_test_case_path_key(tmp_path, capsys):
    paths = _make_source(tmp_path)
    paths["test_case_path"] = None
    dest = tmp_path / "snap"
    save_snapshot(str(dest), paths)
    assert not (dest / "test_cases").exists()
    assert "no test_case_path" in capsys.readouterr().out
