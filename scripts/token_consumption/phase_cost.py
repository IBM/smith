#!/usr/bin/env python3
"""Measure per-phase token/byte cost of the smith workflow under two context regimes.

Arms
----
shared    all phases run in ONE session, chained with `resume`; context accumulates.
isolated  each phase runs in a FRESH session; context is discarded between phases.

Accounting notes (verified empirically against the SDK, not assumed):
  * `ResultMessage.usage` EXCLUDES subagent tokens. `model_usage` includes them.
    We accumulate from model_usage only.
  * Per-step `output_tokens` on AssistantMessage is a placeholder (always 0).
    Output is read from the result message.
  * A fresh session costs ~25k cache-creation tokens before any work is done.
    That boot cost is what the isolated arm pays per phase.
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    ResultMessage,
    AssistantMessage,
    UserMessage,
)

ZERO = {"in": 0, "out": 0, "cache_read": 0, "cache_creation": 0, "usd": 0.0}


def sum_model_usage(mu):
    t = dict(ZERO)
    for v in (mu or {}).values():
        t["in"] += v.get("inputTokens", 0) or 0
        t["out"] += v.get("outputTokens", 0) or 0
        t["cache_read"] += v.get("cacheReadInputTokens", 0) or 0
        t["cache_creation"] += v.get("cacheCreationInputTokens", 0) or 0
        t["usd"] += v.get("costUSD", 0) or 0
    return t


def result_bytes(tur, content):
    """Bytes admitted to context by one tool result."""
    if isinstance(tur, dict):
        n = 0
        for k in ("stdout", "stderr", "originalFile", "newString"):
            v = tur.get(k)
            if isinstance(v, str):
                n += len(v.encode())
        f = tur.get("file")
        if isinstance(f, dict) and isinstance(f.get("content"), str):
            n += len(f["content"].encode())
        if n:
            return n
    return len(content.encode()) if isinstance(content, str) else 0


async def run_phase(name, prompt, *, resume, budget, cwd, model):
    opts = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        cwd=cwd,
        resume=resume,
        max_budget_usd=budget,
        model=model,
        max_turns=60,
    )
    bytes_in, tools, sub_msgs, t0 = 0, {}, 0, time.time()
    rec = None
    async for m in query(prompt=prompt, options=opts):
        if isinstance(m, AssistantMessage):
            if m.parent_tool_use_id:
                sub_msgs += 1
            for b in m.content or []:
                nm = getattr(b, "name", None) or (
                    b.get("name") if isinstance(b, dict) else None
                )
                if nm:
                    tools[nm] = tools.get(nm, 0) + 1
        elif isinstance(m, UserMessage):
            tur = getattr(m, "tool_use_result", None)
            for b in (m.content if isinstance(m.content, list) else []) or []:
                c = (
                    b.get("content")
                    if isinstance(b, dict)
                    else getattr(b, "content", None)
                )
                if isinstance(c, str):
                    bytes_in += result_bytes(tur, c)
        elif isinstance(m, ResultMessage):
            tot = sum_model_usage(m.model_usage)
            rec = {
                "phase": name,
                "session_id": m.session_id,
                "subtype": m.subtype,
                "is_error": m.is_error,
                "turns": m.num_turns,
                "wall_s": round(time.time() - t0, 1),
                "api_ms": m.duration_api_ms,
                **tot,
                "prompt_tokens": tot["in"] + tot["cache_read"] + tot["cache_creation"],
                "bytes_read": bytes_in,
                "tool_calls": tools,
                "subagent_msgs": sub_msgs,
                # usage-field totals kept only to show the subagent undercount
                "usage_field_in": (m.usage or {}).get("input_tokens"),
                "usage_field_out": (m.usage or {}).get("output_tokens"),
                "permission_denials": len(m.permission_denials or []),
            }
    return rec


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["shared", "isolated"], required=True)
    ap.add_argument("--phases", required=True, help="JSON file: [{name, prompt}, ...]")
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--cwd",
        default=str(Path(__file__).resolve().parents[2]),
        help="workspace used by the agent (default: repository root)",
    )
    ap.add_argument("--model", default=None)
    ap.add_argument("--budget", type=float, default=5.0, help="USD cap per phase")
    a = ap.parse_args()

    phases = json.loads(Path(a.phases).read_text())
    out = Path(a.out).open("w")
    session, rows = None, []
    for p in phases:
        rec = await run_phase(
            p["name"],
            p["prompt"],
            resume=session,
            budget=a.budget,
            cwd=a.cwd,
            model=a.model,
        )
        if rec is None:
            print(f"!! {p['name']}: no result message (crash)", file=sys.stderr)
            break
        rec["arm"] = a.arm
        rows.append(rec)
        out.write(json.dumps(rec) + "\n")
        out.flush()
        print(
            f"{a.arm:8s} {rec['phase']:22s} "
            f"prompt={rec['prompt_tokens']:>8,} cc={rec['cache_creation']:>7,} "
            f"cr={rec['cache_read']:>8,} out={rec['out']:>6,} "
            f"bytes={rec['bytes_read']:>8,} ${rec['usd']:.4f} "
            f"{rec['wall_s']}s turns={rec['turns']}"
            + ("  ERROR" if rec["is_error"] else "")
        )
        if a.arm == "shared":
            session = rec["session_id"]
        if rec["is_error"]:
            print("!! stopping: phase errored", file=sys.stderr)
            break

    tot = {
        k: sum(r[k] for r in rows)
        for k in (
            "in",
            "out",
            "cache_read",
            "cache_creation",
            "prompt_tokens",
            "bytes_read",
            "usd",
        )
    }
    print(
        f"\nTOTAL {a.arm}: prompt={tot['prompt_tokens']:,} "
        f"cc={tot['cache_creation']:,} cr={tot['cache_read']:,} "
        f"out={tot['out']:,} bytes={tot['bytes_read']:,} ${tot['usd']:.4f}"
    )
    out.write(json.dumps({"arm": a.arm, "totals": tot, "n_phases": len(rows)}) + "\n")
    out.close()


asyncio.run(main())
