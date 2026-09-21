# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Profile context amplification in Smith's guidance-security workflow.

The profiler runs the same Step A-D workflow in two disposable workspaces:
one persistent Claude conversation (``continuous``) and one fresh conversation
per phase (``isolated``). It stores aggregate usage and file-read byte counts;
prompt and tool-result contents are intentionally never written to disk.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from dotenv import dotenv_values

BYTE_CATEGORIES = (
    "catalog",
    "mcp_source",
    "smith_inputs",
    "chained_artifacts",
    "instructions",
    "unattributed",
)

SMITH_INPUT_NAMES = {"guidance.txt", "system_vars.json", "tool_definitions.json"}
CHAINED_ARTIFACT_NAMES = {
    "architecture.md",
    "policy_guidance_questionnaire.md",
    "threat_model.md",
    "owasp_policy_guidelines.md",
    "guidance_updated.txt",
}


@dataclass(frozen=True)
class Phase:
    key: str
    name: str
    guide: str
    outputs: tuple[str, ...]


PHASES = (
    Phase(
        "A",
        "architecture_analysis",
        "opa_policy/guidelines-security-analysis/steps/architecture_analysis.md",
        ("smith/guidelines-security-analysis/architecture.md",),
    ),
    Phase(
        "B",
        "policy_guidance_questionnaire",
        "opa_policy/guidelines-security-analysis/steps/policy_guidance_questionnaire.md",
        ("smith/guidelines-security-analysis/policy_guidance_questionnaire.md",),
    ),
    Phase(
        "C",
        "threat_model",
        "opa_policy/guidelines-security-analysis/steps/threat_model.md",
        ("smith/guidelines-security-analysis/threat_model.md",),
    ),
    Phase(
        "D",
        "enforcement_mapping",
        "opa_policy/guidelines-security-analysis/steps/enforcement_mapping.md",
        ("smith/guidelines-security-analysis/owasp_policy_guidelines.md",),
    ),
)


@dataclass
class Usage:
    input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def total_input_tokens(self) -> int:
        return (
            self.input_tokens
            + self.cache_read_input_tokens
            + self.cache_creation_input_tokens
        )

    def to_dict(self) -> dict[str, int | float]:
        result = asdict(self)
        result["total_input_tokens"] = self.total_input_tokens
        return result


@dataclass
class PhaseResult:
    phase: str
    name: str
    usage: Usage
    bytes_read: dict[str, int]
    complete: bool
    error: str | None = None
    terminal_reason: str | None = None
    api_error_status: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["usage"] = self.usage.to_dict()
        return result


@dataclass
class VariantResult:
    variant: str
    phases: list[PhaseResult] = field(default_factory=list)
    complete: bool = False
    error: str | None = None

    @property
    def total_usage(self) -> Usage:
        return Usage(
            input_tokens=sum(item.usage.input_tokens for item in self.phases),
            cache_read_input_tokens=sum(
                item.usage.cache_read_input_tokens for item in self.phases
            ),
            cache_creation_input_tokens=sum(
                item.usage.cache_creation_input_tokens for item in self.phases
            ),
            output_tokens=sum(item.usage.output_tokens for item in self.phases),
            cost_usd=sum(item.usage.cost_usd for item in self.phases),
        )

    @property
    def total_bytes_read(self) -> dict[str, int]:
        return {
            category: sum(item.bytes_read[category] for item in self.phases)
            for category in BYTE_CATEGORIES
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "complete": self.complete,
            "error": self.error,
            "phases": [phase.to_dict() for phase in self.phases],
            "total_usage": self.total_usage.to_dict(),
            "total_bytes_read": self.total_bytes_read,
        }


def _int_value(mapping: dict[str, Any], *names: str) -> int:
    for name in names:
        value = mapping.get(name)
        if value is not None:
            return int(value)
    return 0


def usage_from_result(result: Any) -> Usage:
    """Return the cumulative SDK usage snapshot represented by a result."""

    model_usage = getattr(result, "model_usage", None)
    if model_usage:
        values = list(model_usage.values())
        usage = Usage(
            input_tokens=sum(_int_value(item, "inputTokens") for item in values),
            cache_read_input_tokens=sum(
                _int_value(item, "cacheReadInputTokens") for item in values
            ),
            cache_creation_input_tokens=sum(
                _int_value(item, "cacheCreationInputTokens") for item in values
            ),
            output_tokens=sum(_int_value(item, "outputTokens") for item in values),
            cost_usd=sum(float(item.get("costUSD", 0.0)) for item in values),
        )
    else:
        raw = getattr(result, "usage", None) or {}
        usage = Usage(
            input_tokens=_int_value(raw, "input_tokens", "inputTokens"),
            cache_read_input_tokens=_int_value(
                raw, "cache_read_input_tokens", "cacheReadInputTokens"
            ),
            cache_creation_input_tokens=_int_value(
                raw, "cache_creation_input_tokens", "cacheCreationInputTokens"
            ),
            output_tokens=_int_value(raw, "output_tokens", "outputTokens"),
        )

    total_cost = getattr(result, "total_cost_usd", None)
    if total_cost is not None:
        usage.cost_usd = float(total_cost)
    return usage


def usage_delta(current: Usage, previous: Usage) -> Usage:
    """Calculate a phase delta, tolerating an unexpected SDK counter reset."""

    def delta(now: int | float, before: int | float) -> int | float:
        return now - before if now >= before else now

    return Usage(
        input_tokens=int(delta(current.input_tokens, previous.input_tokens)),
        cache_read_input_tokens=int(
            delta(current.cache_read_input_tokens, previous.cache_read_input_tokens)
        ),
        cache_creation_input_tokens=int(
            delta(
                current.cache_creation_input_tokens,
                previous.cache_creation_input_tokens,
            )
        ),
        output_tokens=int(delta(current.output_tokens, previous.output_tokens)),
        cost_usd=float(delta(current.cost_usd, previous.cost_usd)),
    )


def _block_value(block: Any, name: str) -> Any:
    if isinstance(block, dict):
        return block.get(name)
    return getattr(block, name, None)


def _block_kind(block: Any) -> str:
    if isinstance(block, dict):
        return str(block.get("type", ""))
    name = type(block).__name__
    return {
        "ToolUseBlock": "tool_use",
        "ToolResultBlock": "tool_result",
    }.get(name, "")


def _content_bytes(content: Any) -> int:
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content.encode("utf-8"))
    if isinstance(content, list):
        return sum(_content_bytes(item) for item in content)
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return len(content["text"].encode("utf-8"))
        if "content" in content:
            return _content_bytes(content["content"])
        return len(
            json.dumps(content, ensure_ascii=False, sort_keys=True).encode("utf-8")
        )
    return len(str(content).encode("utf-8"))


class ReadByteCollector:
    """Aggregate Read/Grep result bytes without retaining result content."""

    def __init__(self, workspace: Path, target: Path):
        self.workspace = workspace.resolve()
        self.target = (self.workspace / target).resolve()
        self.phase = ""
        self._pending: dict[str, tuple[str, str]] = {}
        self._seen_tool_uses: set[str] = set()
        self._seen_tool_results: set[str] = set()
        self.by_phase: dict[str, dict[str, int]] = {
            phase.key: {category: 0 for category in BYTE_CATEGORIES} for phase in PHASES
        }

    def set_phase(self, phase: str) -> None:
        self.phase = phase

    def consume(self, message: Any) -> None:
        blocks = getattr(message, "content", None)
        if not isinstance(blocks, list):
            return
        for block in blocks:
            kind = _block_kind(block)
            if kind == "tool_use":
                self._remember_tool_use(block)
            elif kind == "tool_result":
                self._record_tool_result(block)

    def _remember_tool_use(self, block: Any) -> None:
        name = str(_block_value(block, "name") or "")
        if name not in {"Read", "Grep"}:
            return
        tool_id = str(_block_value(block, "id") or "")
        if not tool_id or tool_id in self._seen_tool_uses:
            return
        self._seen_tool_uses.add(tool_id)
        tool_input = _block_value(block, "input") or {}
        raw_path = tool_input.get("file_path") or tool_input.get("path") or ""
        self._pending[tool_id] = (self.phase, self.classify_path(str(raw_path)))

    def _record_tool_result(self, block: Any) -> None:
        tool_id = str(_block_value(block, "tool_use_id") or "")
        if not tool_id or tool_id in self._seen_tool_results:
            return
        self._seen_tool_results.add(tool_id)
        pending = self._pending.pop(tool_id, None)
        if not pending:
            return
        phase, category = pending
        self.by_phase[phase][category] += _content_bytes(_block_value(block, "content"))

    def classify_path(self, raw_path: str) -> str:
        if not raw_path:
            return "unattributed"
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.workspace / path
        try:
            resolved = path.resolve()
            relative = resolved.relative_to(self.workspace)
        except (OSError, ValueError):
            return "unattributed"

        relative_text = relative.as_posix()
        if relative.name == "owasp_10_ai_catalog.json":
            return "catalog"
        if relative.name in CHAINED_ARTIFACT_NAMES:
            return "chained_artifacts"
        if relative.name in SMITH_INPUT_NAMES and resolved.is_relative_to(self.target):
            return "smith_inputs"
        if relative.name in {"SKILL.md", "CLAUDE.md"} or relative_text.startswith(
            "opa_policy/guidelines-security-analysis/"
        ):
            return "instructions"
        if resolved.is_relative_to(self.target):
            return "mcp_source"
        return "unattributed"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _safe_relative_target(repo: Path, target: str) -> Path:
    candidate = Path(target)
    resolved = (
        (repo / candidate).resolve()
        if not candidate.is_absolute()
        else candidate.resolve()
    )
    try:
        relative = resolved.relative_to(repo.resolve())
    except ValueError as exc:
        raise ValueError("--target must be inside the Smith repository") from exc
    if not resolved.is_dir():
        raise ValueError(f"target directory does not exist: {target}")
    return relative


def _ignored_paths(directory: str, names: list[str]) -> set[str]:
    ignored = {
        name
        for name in names
        if name
        in {
            ".env",
            ".git",
            ".venv",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
        }
        or name.endswith(".pyc")
    }
    path = Path(directory)
    if path.name == "smith":
        ignored.update(
            name
            for name in names
            if name in {"guidelines-security-analysis", "guidance_updated.txt"}
        )
    return ignored


def create_snapshot(repo: Path, target: Path, destination: Path) -> None:
    """Copy only the instructions, catalog, and target needed by the run."""

    destination.mkdir(parents=True)
    for filename in ("SKILL.md", "CLAUDE.md"):
        source = repo / filename
        if source.exists():
            shutil.copy2(source, destination / filename)

    project_instructions = repo / ".claude" / "CLAUDE.md"
    if project_instructions.exists():
        output = destination / ".claude" / "CLAUDE.md"
        output.parent.mkdir(parents=True)
        shutil.copy2(project_instructions, output)

    guide_source = repo / "opa_policy" / "guidelines-security-analysis"
    shutil.copytree(
        guide_source,
        destination / "opa_policy" / "guidelines-security-analysis",
        ignore=_ignored_paths,
    )

    catalog_source = repo / "src" / "smith" / "data" / "owasp_10_ai_catalog.json"
    catalog_output = destination / "src" / "smith" / "data" / catalog_source.name
    catalog_output.parent.mkdir(parents=True)
    shutil.copy2(catalog_source, catalog_output)

    shutil.copytree(
        repo / target,
        destination / target,
        ignore=_ignored_paths,
    )


def _runtime_env(repo: Path, workspace: Path, target: Path) -> dict[str, str]:
    values = {
        key: value
        for key, value in dotenv_values(repo / ".env").items()
        if value is not None
    }
    environment = {**values, **os.environ}
    environment.update(
        {
            "BASE_URL": f"{workspace}{os.sep}",
            "TARGET_AGENT_PATH": f"{target.as_posix().rstrip('/')}/",
            "GUIDANCE_FILE": f"{target.as_posix().rstrip('/')}/smith/guidance.txt",
            "SYSTEM_VAR_FILE": (
                f"{target.as_posix().rstrip('/')}/smith/system_vars.json"
            ),
        }
    )

    mcp_cwd = environment.get("MCP_CWD")
    if mcp_cwd:
        configured = Path(mcp_cwd)
        if configured.is_absolute():
            try:
                configured = configured.resolve().relative_to(repo.resolve())
            except ValueError as exc:
                raise ValueError(
                    "MCP_CWD must be inside the repository for an isolated profile"
                ) from exc
        # smith.cli joins BASE_URL and MCP_CWD itself, so keep this relative.
        environment["MCP_CWD"] = configured.as_posix()
    return environment


def _redact(text: str, environment: dict[str, str]) -> str:
    redacted = text
    for key, value in environment.items():
        upper = key.upper()
        if value and any(
            word in upper for word in ("KEY", "TOKEN", "SECRET", "PASSWORD")
        ):
            redacted = redacted.replace(value, "[REDACTED]")
    return redacted


def run_prerequisites(repo: Path, workspace: Path, target: Path) -> None:
    environment = _runtime_env(repo, workspace, target)
    for flag in ("get_current_agent", "get_mcp_parameter"):
        completed = subprocess.run(
            [sys.executable, "-m", "smith.cli", "--flag", flag],
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if completed.returncode:
            details = _redact(
                (completed.stderr or completed.stdout)[-2000:], environment
            )
            raise RuntimeError(
                f"Smith prerequisite '{flag}' failed with exit code "
                f"{completed.returncode}:\n{details}"
            )


def _phase_prompt(phase: Phase, target: Path) -> str:
    overall = "opa_policy/guidelines-security-analysis/guidelines-security-analysis.md"
    return f"""Run only Step {phase.key} ({phase.name}) of Smith's Security-Grounded Guidance Analysis.

This is an autonomous profiling run. Do not ask questions, do not run another phase, and do not merge guidance or create a policy. The Smith CLI prerequisites have already completed.

First read `SKILL.md` for Smith's routing contract, then read and strictly follow `{overall}` and `{phase.guide}`. The target MCP server is `{target.as_posix()}`. Write only the designated Step {phase.key} output under that target. Do not modify source inputs. Return only a brief completion status after writing the artifact.
"""


def _sdk_client(workspace: Path, budget: float | None, model: str | None) -> Any:
    try:
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
    except ImportError as exc:
        raise RuntimeError(
            "The context profiler requires the optional dependency: "
            "uv sync --extra context-profile"
        ) from exc

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep", "Write", "Edit"],
        disallowed_tools=["Bash", "WebFetch", "WebSearch"],
        permission_mode="acceptEdits",
        cwd=workspace,
        max_turns=120,
        max_budget_usd=budget,
        model=model,
        extra_args={"no-session-persistence": None},
    )
    return ClaudeSDKClient(options=options)


async def _receive_phase(
    client: Any,
    prompt: str,
    collector: ReadByteCollector,
    timeout_seconds: float,
) -> Any:
    result = None
    async with asyncio.timeout(timeout_seconds):
        await client.query(prompt)
        async for message in client.receive_response():
            collector.consume(message)
            if type(message).__name__ == "ResultMessage":
                result = message
    if result is None:
        raise RuntimeError("Claude Agent SDK returned no ResultMessage")
    return result


def _phase_is_complete(
    workspace: Path, target: Path, phase: Phase, result: Any
) -> bool:
    if bool(getattr(result, "is_error", False)):
        return False
    return all((workspace / target / output).is_file() for output in phase.outputs)


def _phase_error(result: Any, complete: bool) -> str | None:
    if complete:
        return None
    subtype = str(getattr(result, "subtype", "unknown"))
    if bool(getattr(result, "is_error", False)):
        return f"SDK result: {subtype}"
    return f"required artifact was not produced (SDK result: {subtype})"


async def run_variant(
    variant: str,
    workspace: Path,
    target: Path,
    max_budget_usd: float | None,
    model: str | None = None,
    client_factory: Callable[[Path, float | None, str | None], Any] = _sdk_client,
    phase_timeout_seconds: float = 1800,
) -> VariantResult:
    collector = ReadByteCollector(workspace, target)
    report = VariantResult(variant=variant)
    previous = Usage()

    try:
        if variant == "continuous":
            async with client_factory(workspace, max_budget_usd, model) as client:
                for phase in PHASES:
                    print(f"[{variant}] Step {phase.key} starting", flush=True)
                    collector.set_phase(phase.key)
                    result = await _receive_phase(
                        client,
                        _phase_prompt(phase, target),
                        collector,
                        phase_timeout_seconds,
                    )
                    cumulative = usage_from_result(result)
                    phase_usage = usage_delta(cumulative, previous)
                    previous = cumulative
                    complete = _phase_is_complete(workspace, target, phase, result)
                    report.phases.append(
                        PhaseResult(
                            phase=phase.key,
                            name=phase.name,
                            usage=phase_usage,
                            bytes_read=dict(collector.by_phase[phase.key]),
                            complete=complete,
                            error=_phase_error(result, complete),
                            terminal_reason=getattr(result, "terminal_reason", None),
                            api_error_status=getattr(result, "api_error_status", None),
                        )
                    )
                    print(
                        f"[{variant}] Step {phase.key} "
                        f"{'complete' if complete else 'incomplete'}",
                        flush=True,
                    )
                    if not complete:
                        break
        elif variant == "isolated":
            spent = 0.0
            for phase in PHASES:
                print(f"[{variant}] Step {phase.key} starting", flush=True)
                remaining = (
                    None if max_budget_usd is None else max(max_budget_usd - spent, 0.0)
                )
                if remaining == 0:
                    report.error = "variant budget exhausted before all phases"
                    break
                collector.set_phase(phase.key)
                async with client_factory(workspace, remaining, model) as client:
                    result = await _receive_phase(
                        client,
                        _phase_prompt(phase, target),
                        collector,
                        phase_timeout_seconds,
                    )
                phase_usage = usage_from_result(result)
                spent += phase_usage.cost_usd
                complete = _phase_is_complete(workspace, target, phase, result)
                report.phases.append(
                    PhaseResult(
                        phase=phase.key,
                        name=phase.name,
                        usage=phase_usage,
                        bytes_read=dict(collector.by_phase[phase.key]),
                        complete=complete,
                        error=_phase_error(result, complete),
                        terminal_reason=getattr(result, "terminal_reason", None),
                        api_error_status=getattr(result, "api_error_status", None),
                    )
                )
                print(
                    f"[{variant}] Step {phase.key} "
                    f"{'complete' if complete else 'incomplete'}",
                    flush=True,
                )
                if not complete:
                    break
        else:
            raise ValueError(f"unknown variant: {variant}")
    except Exception as exc:  # Preserve partial aggregate data for failed live runs.
        report.error = f"{type(exc).__name__}: profiling failed"

    report.complete = len(report.phases) == len(PHASES) and all(
        phase.complete for phase in report.phases
    )
    if not report.complete and report.error is None:
        report.error = "one or more phases did not produce the required artifact"
    return report


def _ratio(numerator: int | float, denominator: int | float) -> str:
    if denominator == 0:
        return "n/a"
    return f"{numerator / denominator:.2f}x"


def _dominant_category(result: VariantResult) -> str:
    totals = result.total_bytes_read
    category, byte_count = max(totals.items(), key=lambda item: item[1])
    return f"{category} ({byte_count:,} bytes)"


def comparison_markdown(
    run_id: str, target: Path, continuous: VariantResult, isolated: VariantResult
) -> str:
    lines = [
        "# Smith context profile",
        "",
        f"- Run: `{run_id}`",
        f"- Target: `{target.as_posix()}`",
        f"- Continuous complete: `{continuous.complete}`",
        f"- Isolated complete: `{isolated.complete}`",
        "",
        "| Phase | Continuous input | Isolated input | Continuous output | Isolated output | Continuous bytes | Isolated bytes |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    continuous_by_phase = {item.phase: item for item in continuous.phases}
    isolated_by_phase = {item.phase: item for item in isolated.phases}
    for phase in PHASES:
        left = continuous_by_phase.get(phase.key)
        right = isolated_by_phase.get(phase.key)
        lines.append(
            "| {phase} | {li} | {ri} | {lo} | {ro} | {lb} | {rb} |".format(
                phase=phase.key,
                li=f"{left.usage.total_input_tokens:,}" if left else "—",
                ri=f"{right.usage.total_input_tokens:,}" if right else "—",
                lo=f"{left.usage.output_tokens:,}" if left else "—",
                ro=f"{right.usage.output_tokens:,}" if right else "—",
                lb=f"{sum(left.bytes_read.values()):,}" if left else "—",
                rb=f"{sum(right.bytes_read.values()):,}" if right else "—",
            )
        )

    left_usage = continuous.total_usage
    right_usage = isolated.total_usage
    lines.extend(
        [
            "",
            "## Totals",
            "",
            "| Variant | Input tokens | Output tokens | Cost (USD) | Bytes read | Dominant byte category |",
            "|---|---:|---:|---:|---:|---|",
            (
                f"| Continuous | {left_usage.total_input_tokens:,} | "
                f"{left_usage.output_tokens:,} | ${left_usage.cost_usd:.4f} | "
                f"{sum(continuous.total_bytes_read.values()):,} | "
                f"{_dominant_category(continuous)} |"
            ),
            (
                f"| Isolated | {right_usage.total_input_tokens:,} | "
                f"{right_usage.output_tokens:,} | ${right_usage.cost_usd:.4f} | "
                f"{sum(isolated.total_bytes_read.values()):,} | "
                f"{_dominant_category(isolated)} |"
            ),
            "",
            "## Isolated / continuous ratios",
            "",
            f"- Input tokens: {_ratio(right_usage.total_input_tokens, left_usage.total_input_tokens)}",
            f"- Output tokens: {_ratio(right_usage.output_tokens, left_usage.output_tokens)}",
            f"- Cost: {_ratio(right_usage.cost_usd, left_usage.cost_usd)}",
            "",
            "## Bytes read by category",
            "",
            "| Category | Continuous | Isolated |",
            "|---|---:|---:|",
        ]
    )
    for category in BYTE_CATEGORIES:
        lines.append(
            f"| {category} | {continuous.total_bytes_read[category]:,} | "
            f"{isolated.total_bytes_read[category]:,} |"
        )
    lines.extend(
        [
            "",
            "Byte counts are UTF-8 sizes of observed Read/Grep tool-result payloads. Bash reads are disabled; unresolvable paths are classified as `unattributed`.",
        ]
    )
    if not (continuous.complete and isolated.complete):
        lines.extend(
            [
                "",
                "> This pair is incomplete and must not be used as a benchmark comparison.",
            ]
        )
    return "\n".join(lines) + "\n"


async def run_pairs(args: argparse.Namespace) -> int:
    repo = _repo_root()
    target = _safe_relative_target(repo, args.target)
    output_root = Path(args.output).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    overall_success = True
    for pair_number in range(1, args.pairs + 1):
        run_id = (
            datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            + f"-{pair_number}-{uuid.uuid4().hex[:8]}"
        )
        run_directory = output_root / run_id
        run_directory.mkdir()

        with tempfile.TemporaryDirectory(prefix="smith-context-profile-") as temp:
            temp_root = Path(temp)
            snapshot = temp_root / "snapshot"
            create_snapshot(repo, target, snapshot)
            workspaces = {
                variant: temp_root / variant for variant in ("continuous", "isolated")
            }
            for workspace in workspaces.values():
                shutil.copytree(snapshot, workspace)
                run_prerequisites(repo, workspace, target)

            print(f"[{run_id}] running continuous workflow", flush=True)
            continuous = await run_variant(
                "continuous",
                workspaces["continuous"],
                target,
                args.max_budget_usd,
                args.model,
                phase_timeout_seconds=args.phase_timeout_seconds,
            )
            print(f"[{run_id}] running isolated workflow", flush=True)
            isolated = await run_variant(
                "isolated",
                workspaces["isolated"],
                target,
                args.max_budget_usd,
                args.model,
                phase_timeout_seconds=args.phase_timeout_seconds,
            )

            payload = {
                "schema_version": 1,
                "run_id": run_id,
                "created_at": datetime.now(UTC).isoformat(),
                "target": target.as_posix(),
                "model": args.model or "default",
                "budget_usd_per_variant": args.max_budget_usd,
                "stores_raw_content": False,
                "variants": [continuous.to_dict(), isolated.to_dict()],
            }
            (run_directory / "results.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            (run_directory / "comparison.md").write_text(
                comparison_markdown(run_id, target, continuous, isolated),
                encoding="utf-8",
            )

        pair_success = continuous.complete and isolated.complete
        overall_success = overall_success and pair_success
        state = "complete" if pair_success else "incomplete"
        print(f"[{run_id}] {state}: {run_directory / 'comparison.md'}", flush=True)

    return 0 if overall_success else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smith-context-profile",
        description=(
            "Compare continuous and isolated-context Smith guidance-security runs."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="run one or more paired profiles")
    run.add_argument("--target", required=True, help="repo-relative MCP server path")
    run.add_argument("--pairs", type=int, default=1, help="number of run pairs")
    run.add_argument(
        "--max-budget-usd",
        type=float,
        default=None,
        help="maximum Agent SDK cost for each workflow variant",
    )
    run.add_argument("--model", default=None, help="Claude model override")
    run.add_argument(
        "--phase-timeout-seconds",
        type=float,
        default=1800,
        help="timeout for each phase (default: 1800)",
    )
    run.add_argument(
        "--output",
        default=str(Path(tempfile.gettempdir()) / "smith-context-profile"),
        help="directory for sanitized JSON and Markdown reports",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.pairs < 1:
        parser.error("--pairs must be at least 1")
    if args.max_budget_usd is not None and args.max_budget_usd <= 0:
        parser.error("--max-budget-usd must be greater than zero")
    if args.phase_timeout_seconds <= 0:
        parser.error("--phase-timeout-seconds must be greater than zero")
    try:
        raise SystemExit(asyncio.run(run_pairs(args)))
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main()
