#!/usr/bin/env python3
"""Per-phase cost of the smith workflow, measured in streaming input mode.

One `query()` call, one gated turn per phase. The isolated arm injects `/clear`
between phases, so process lifetime, loaded skills and the system-prompt cache
are held CONSTANT across arms and the only variable is whether conversation
context carries forward.

Verified mechanics this relies on (measured, not assumed):
  * `usage` on a result is PER TURN, main loop only (excludes subagents).
  * `model_usage` / `total_cost_usd` are RUNNING TOTALS for the call so far,
    so per-phase figures are DIFFERENCES, never sums.
      measured: mu.in 2887 -> 2919 across two turns, turn_usage_in = 32.
  * `/clear` resets those running totals to zero and issues a new session_id.
    Its own result reports turns=0 and all-zero usage: skip it, or it lands in
    the output as a phantom zero-cost phase.
  * Streaming input BATCHES: if you push turns faster than the agent consumes
    them, two phases collapse into one result (observed: turns=2 on result#1).
    The gate below sends exactly one turn at a time.
  * Whole-call total = sum of the last result before each reset, plus the
    final result. Every other result is superseded.

This measures the LOWER bound on isolation cost. phase_cost.py, which spawns a
fresh session per phase, measures the upper bound; a fresh process additionally
pays ~25k cache-creation tokens to boot.
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
    ConversationResetMessage,
)

KEYS = ("in", "out", "cache_read", "cache_creation", "usd")
FIELD = {
    "in": "inputTokens",
    "out": "outputTokens",
    "cache_read": "cacheReadInputTokens",
    "cache_creation": "cacheCreationInputTokens",
    "usd": "costUSD",
}


def cum(mu):
    t = {k: 0 for k in KEYS}
    for v in (mu or {}).values():
        for k in KEYS:
            t[k] += v.get(FIELD[k], 0) or 0
    return t


def result_bytes(tur, content):
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


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["shared", "isolated"], required=True)
    ap.add_argument("--phases", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--cwd",
        default=str(Path(__file__).resolve().parents[2]),
        help="workspace used by the agent (default: repository root)",
    )
    ap.add_argument("--model", default=None)
    ap.add_argument(
        "--budget",
        type=float,
        default=10.0,
        help="USD cap on the running total; NOTE /clear restarts it",
    )
    a = ap.parse_args()

    phases = json.loads(Path(a.phases).read_text())
    # build the turn list: phase prompts, with /clear between them for isolated
    turns, labels = [], []
    for i, p in enumerate(phases):
        if a.arm == "isolated" and i > 0:
            turns.append("/clear")
            labels.append(None)
        turns.append(p["prompt"])
        labels.append(p["name"])

    gate = asyncio.Queue()

    async def gen():
        last = len(turns) - 1
        for i, t in enumerate(turns):
            yield {"type": "user", "message": {"role": "user", "content": t}}
            # one turn in flight: no batching. Do NOT wait after the final turn,
            # or the generator is still awaiting when the SDK closes the stream
            # ("aclose(): asynchronous generator is already running").
            if i < last:
                await gate.get()

    opts = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        cwd=a.cwd,
        model=a.model,
        max_budget_usd=a.budget,
        max_turns=60,
    )

    out = Path(a.out).open("w")
    base = {k: 0 for k in KEYS}  # cumulative at end of previous phase
    seg_last = {k: 0 for k in KEYS}  # last cumulative seen in this segment
    seg_closed = {k: 0 for k in KEYS}  # sum of segments already reset away
    idx, rows, bytes_in, tools, subs, t0 = 0, [], 0, {}, 0, time.time()

    async for m in query(prompt=gen(), options=opts):
        if isinstance(m, ConversationResetMessage):
            for k in KEYS:
                seg_closed[k] += seg_last[k]
            base = {k: 0 for k in KEYS}
            seg_last = {k: 0 for k in KEYS}
            print(f"   -- reset -> {m.new_conversation_id[:8]}", file=sys.stderr)

        elif isinstance(m, AssistantMessage):
            if m.parent_tool_use_id:
                subs += 1
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
            c = cum(m.model_usage)
            label = labels[idx] if idx < len(labels) else "?"
            idx += 1
            gate.put_nowait(None)  # release the next turn
            if label is None:  # the /clear turn's own result
                continue
            delta = {k: round(c[k] - base[k], 6) for k in KEYS}
            base, seg_last = c, c
            rec = {
                "arm": a.arm,
                "phase": label,
                "session_id": m.session_id,
                "subtype": m.subtype,
                "is_error": m.is_error,
                "turns": m.num_turns,
                "wall_s": round(time.time() - t0, 1),
                **delta,
                "prompt_tokens": delta["in"]
                + delta["cache_read"]
                + delta["cache_creation"],
                "bytes_read": bytes_in,
                "tool_calls": dict(tools),
                "subagent_msgs": subs,
                "turn_usage_in": (m.usage or {}).get("input_tokens"),
                "permission_denials": len(m.permission_denials or []),
            }
            rows.append(rec)
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(
                f"{a.arm:8s} {label:22s} prompt={rec['prompt_tokens']:>8,} "
                f"cc={delta['cache_creation']:>7,} cr={delta['cache_read']:>8,} "
                f"in={delta['in']:>6,} out={delta['out']:>5,} "
                f"bytes={bytes_in:>8,} ${delta['usd']:.4f} {rec['wall_s']}s"
                + ("  ERROR" if m.is_error else ""),
                flush=True,
            )
            bytes_in, tools, subs = 0, {}, 0  # reset per-phase stream counters

    grand = {k: round(seg_closed[k] + seg_last[k], 6) for k in KEYS}
    tot = {k: sum(r[k] for r in rows) for k in ("prompt_tokens", "bytes_read")}
    print(
        f"\nTOTAL {a.arm}: prompt={tot['prompt_tokens']:,} "
        f"bytes={tot['bytes_read']:,} ${grand['usd']:.4f} "
        f"(cc={grand['cache_creation']:,} cr={grand['cache_read']:,})"
    )
    out.write(
        json.dumps(
            {
                "arm": a.arm,
                "grand_total": grand,
                "summed_phases": tot,
                "n_phases": len(rows),
            }
        )
        + "\n"
    )
    out.close()


asyncio.run(main())
