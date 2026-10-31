# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
"""Rendering Claude Code's stream-json event feed into a readable transcript."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Partial deltas are skipped: the completed message repeats the full text.
_SKIP_TYPES = {"stream_event", "message_start", "content_block_delta"}
# Preferred fields for a one-line summary of a tool's input.
_DETAIL_FIELDS = ("command", "file_path", "pattern", "prompt")


def brief(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[:limit] + "…"


def _tool_detail(inp: dict[str, Any]) -> str:
    for field in _DETAIL_FIELDS:
        if field in inp:
            return brief(inp[field])
    return brief(inp)


def _tool_result_text(block: dict[str, Any]) -> str:
    content = block.get("content")
    if isinstance(content, list):
        content = " ".join(c.get("text", "") for c in content
                           if isinstance(c, dict))
    return brief(content, 200)


def render(events: list[dict[str, Any]] | None = None, *,
           raw: str | None = None) -> str:
    """Render an event list (or raw NDJSON text) to a transcript."""
    lines: list[str] = []
    seen: set[str] = set()

    if events is None:
        events = []
        for line in (raw or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                # Not JSON (e.g. a startup warning) — keep it verbatim.
                lines.append(line)

    for ev in events:
        kind = ev.get("type")
        if kind in _SKIP_TYPES:
            continue

        if kind == "assistant":
            for block in ev.get("message", {}).get("content", []) or []:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "thinking":
                    if thought := (block.get("thinking") or "").strip():
                        lines.append(f"[thinking] {thought}\n")
                elif btype == "text":
                    text = (block.get("text") or "").strip()
                    if text and text not in seen:
                        seen.add(text)
                        lines.append(text + "\n")
                elif btype == "tool_use":
                    name = block.get("name", "?")
                    detail = _tool_detail(block.get("input") or {})
                    lines.append(f"[tool] {name}: {detail}")

        elif kind == "user":
            for block in ev.get("message", {}).get("content", []) or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    flag = " (error)" if block.get("is_error") else ""
                    lines.append(f"[result{flag}] {_tool_result_text(block)}\n")

        elif kind == "result":
            if (res := (ev.get("result") or "").strip()) and res not in seen:
                lines.append(res + "\n")
            bits = []
            if (turns := ev.get("num_turns")) is not None:
                bits.append(f"turns={turns}")
            if (cost := ev.get("total_cost_usd")) is not None:
                bits.append(f"cost=${cost:.4f}")
            if ev.get("is_error"):
                bits.append("is_error=true")
            if bits:
                lines.append("[run] " + "  ".join(bits))

    return "\n".join(lines) + ("\n" if lines else "")


def live_line(raw: str) -> str:
    """One short progress line for a single streamed event, or empty string"""
    raw = raw.strip()
    if not raw:
        return ""
    try:
        ev = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    if not isinstance(ev, dict) or ev.get("type") in _SKIP_TYPES:
        return ""

    kind = ev.get("type")
    if kind == "assistant":
        for block in ev.get("message", {}).get("content", []) or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                return (f"{block.get('name', '?')}: "
                        f"{_tool_detail(block.get('input') or {})}")
            if block.get("type") == "text":
                if text := (block.get("text") or "").strip():
                    return brief(text, 140)
    elif kind == "user":
        for block in ev.get("message", {}).get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                flag = "error: " if block.get("is_error") else ""
                return f"{flag}{brief(_tool_result_text(block), 120)}"
    elif kind == "result":
        bits = []
        if (turns := ev.get("num_turns")) is not None:
            bits.append(f"turns={turns}")
        if (cost := ev.get("total_cost_usd")) is not None:
            bits.append(f"cost=${cost:.4f}")
        return "done  " + "  ".join(bits) if bits else "done"
    return ""


def render_file(path: Path) -> str:
    try:
        return render(raw=path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return ""


def session_id(path: Path) -> str | None:
    """The Claude session id from a trace's `result` event, or None."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    found: str | None = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Prefer the result event's id; fall back to any event carrying one, so
        # a step killed before it emitted a result can still be continued.
        if sid := ev.get("session_id"):
            if ev.get("type") == "result":
                return sid
            found = found or sid
    return found


def usage_totals(path: Path) -> dict[str, float | int]:
    """Extract per-run cost/turn totals from a trace, for cost reporting."""
    totals: dict[str, float | int] = {}
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return totals
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") != "result":
            continue
        # Cost is cumulative within a resumed session; token usage is per run.
        if (cost := ev.get("total_cost_usd")) is not None:
            totals["cost_usd"] = cost
        if (turns := ev.get("num_turns")) is not None:
            totals["turns"] = turns
        if isinstance(usage := ev.get("usage"), dict):
            for key in ("input_tokens", "output_tokens",
                        "cache_read_input_tokens",
                        "cache_creation_input_tokens"):
                if (v := usage.get(key)) is not None:
                    totals[key] = v
    return totals
