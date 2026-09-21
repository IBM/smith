# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Offline tests for the Smith context profiler."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from smith.tools.context_profile import (
    BYTE_CATEGORIES,
    PHASES,
    ReadByteCollector,
    Usage,
    create_snapshot,
    run_variant,
    usage_delta,
    usage_from_result,
)

pytestmark = pytest.mark.unit


def test_usage_uses_model_totals_and_calculates_cumulative_delta():
    first = SimpleNamespace(
        model_usage={
            "sonnet": {
                "inputTokens": 10,
                "cacheReadInputTokens": 20,
                "cacheCreationInputTokens": 30,
                "outputTokens": 4,
                "costUSD": 0.1,
            }
        },
        usage=None,
        total_cost_usd=0.1,
    )
    second = SimpleNamespace(
        model_usage={
            "sonnet": {
                "inputTokens": 25,
                "cacheReadInputTokens": 50,
                "cacheCreationInputTokens": 40,
                "outputTokens": 10,
                "costUSD": 0.25,
            }
        },
        usage=None,
        total_cost_usd=0.25,
    )

    first_usage = usage_from_result(first)
    delta = usage_delta(usage_from_result(second), first_usage)

    assert first_usage.total_input_tokens == 60
    assert delta == Usage(
        input_tokens=15,
        cache_read_input_tokens=30,
        cache_creation_input_tokens=10,
        output_tokens=6,
        cost_usd=0.15,
    )


def test_read_collector_classifies_results_and_deduplicates_messages(tmp_path):
    target = Path("examples/demo")
    collector = ReadByteCollector(tmp_path, target)
    collector.set_phase("C")

    tool_uses = SimpleNamespace(
        message_id="assistant-1",
        content=[
            {
                "type": "tool_use",
                "id": "catalog-read",
                "name": "Read",
                "input": {"file_path": "src/smith/data/owasp_10_ai_catalog.json"},
            },
            {
                "type": "tool_use",
                "id": "artifact-read",
                "name": "Read",
                "input": {
                    "file_path": (
                        "examples/demo/smith/guidelines-security-analysis/"
                        "architecture.md"
                    )
                },
            },
        ],
    )
    collector.consume(tool_uses)
    collector.consume(tool_uses)
    collector.consume(
        SimpleNamespace(
            message_id="assistant-1",
            content=[
                {
                    "type": "tool_use",
                    "id": "source-read",
                    "name": "Read",
                    "input": {"file_path": "examples/demo/server.py"},
                }
            ],
        )
    )
    collector.consume(
        SimpleNamespace(
            content=[
                {
                    "type": "tool_result",
                    "tool_use_id": "catalog-read",
                    "content": "catalog",
                },
                {
                    "type": "tool_result",
                    "tool_use_id": "artifact-read",
                    "content": [{"type": "text", "text": "arch"}],
                },
                {
                    "type": "tool_result",
                    "tool_use_id": "source-read",
                    "content": "source",
                },
            ]
        )
    )

    assert collector.by_phase["C"]["catalog"] == len(b"catalog")
    assert collector.by_phase["C"]["chained_artifacts"] == len(b"arch")
    assert collector.by_phase["C"]["mcp_source"] == len(b"source")
    assert sum(collector.by_phase["C"].values()) == len(b"catalogarchsource")


def test_snapshot_excludes_credentials_and_existing_analysis(tmp_path):
    repo = tmp_path / "repo"
    target = Path("examples/demo")
    (repo / ".claude").mkdir(parents=True)
    (repo / "opa_policy/guidelines-security-analysis/steps").mkdir(parents=True)
    (repo / "src/smith/data").mkdir(parents=True)
    (repo / target / "smith/guidelines-security-analysis").mkdir(parents=True)

    (repo / "SKILL.md").write_text("skill", encoding="utf-8")
    (repo / "CLAUDE.md").write_text("instructions", encoding="utf-8")
    (repo / ".claude/CLAUDE.md").write_text("project", encoding="utf-8")
    (repo / "opa_policy/guidelines-security-analysis/guide.md").write_text(
        "guide", encoding="utf-8"
    )
    (repo / "src/smith/data/owasp_10_ai_catalog.json").write_text(
        "{}", encoding="utf-8"
    )
    (repo / target / "server.py").write_text("pass", encoding="utf-8")
    (repo / target / ".env").write_text("SECRET=value", encoding="utf-8")
    (repo / target / "smith/guidance.txt").write_text("rule", encoding="utf-8")
    (repo / target / "smith/guidance_updated.txt").write_text(
        "proposal", encoding="utf-8"
    )
    (repo / target / "smith/guidelines-security-analysis/architecture.md").write_text(
        "old artifact", encoding="utf-8"
    )

    destination = tmp_path / "snapshot"
    create_snapshot(repo, target, destination)

    assert (destination / target / "server.py").is_file()
    assert (destination / target / "smith/guidance.txt").is_file()
    assert not (destination / target / ".env").exists()
    assert not (destination / target / "smith/guidance_updated.txt").exists()
    assert not (destination / target / "smith/guidelines-security-analysis").exists()


class ResultMessage:
    def __init__(self, cumulative: int, cost: float):
        self.model_usage = {
            "sonnet": {
                "inputTokens": cumulative,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 0,
                "outputTokens": cumulative // 10,
                "costUSD": cost,
            }
        }
        self.total_cost_usd = cost
        self.is_error = False
        self.subtype = "success"


class FakeClient:
    def __init__(self, workspace: Path, target: Path, cumulative: bool):
        self.workspace = workspace
        self.target = target
        self.cumulative = cumulative
        self.turn = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def query(self, prompt: str):
        phase = next(item for item in PHASES if f"Step {item.key}" in prompt)
        for output in phase.outputs:
            path = self.workspace / self.target / output
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("generated", encoding="utf-8")
        self.turn += 1

    async def receive_response(self):
        total = self.turn * 100 if self.cumulative else 100
        cost = self.turn * 0.1 if self.cumulative else 0.1
        yield ResultMessage(total, cost)


@pytest.mark.asyncio
async def test_continuous_and_isolated_runs_produce_comparable_phase_totals(tmp_path):
    target = Path("examples/demo")
    budgets: list[float | None] = []

    def continuous_factory(workspace, budget, model):
        budgets.append(budget)
        assert model == "test-model"
        return FakeClient(workspace, target, cumulative=True)

    continuous = await run_variant(
        "continuous",
        tmp_path / "continuous",
        target,
        2.0,
        "test-model",
        continuous_factory,
    )

    def isolated_factory(workspace, budget, model):
        budgets.append(budget)
        return FakeClient(workspace, target, cumulative=False)

    isolated = await run_variant(
        "isolated",
        tmp_path / "isolated",
        target,
        2.0,
        "test-model",
        isolated_factory,
    )

    assert continuous.complete is True
    assert isolated.complete is True
    assert [phase.usage.input_tokens for phase in continuous.phases] == [100] * 4
    assert [phase.usage.input_tokens for phase in isolated.phases] == [100] * 4
    assert continuous.total_usage.cost_usd == pytest.approx(0.4)
    assert isolated.total_usage.cost_usd == pytest.approx(0.4)
    assert budgets == [2.0, 2.0, 1.9, 1.8, 1.7]
    assert all(
        set(phase.bytes_read) == set(BYTE_CATEGORIES) for phase in continuous.phases
    )
