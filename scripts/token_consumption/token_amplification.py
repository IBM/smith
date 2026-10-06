#!/usr/bin/env python3
"""Measure context amplification from Claude Code inference-call telemetry.

Each assistant entry in a Claude Code transcript carries a `usage` block that is
the real per-API-call accounting:

    input_tokens                 uncached tail of the prompt
    cache_creation_input_tokens  newly written to the cache this call
    cache_read_input_tokens      prefix replayed from cache
    output_tokens                generated

Full prompt for a call = input + cache_creation + cache_read.

Amplification is the ratio between total prompt tokens the model was asked to
process across a session and the amount of distinct context that ever existed.
A single-shot call has amplification 1.0; an agent loop that resends its whole
history every step grows it roughly linearly in the number of steps.
"""

import json
import sys
import glob
import os


def calls_from(path):
    """Yield one record per inference call in a transcript."""
    seen = set()
    with open(path) as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("type") != "assistant":
                continue
            msg = d.get("message") or {}
            u = msg.get("usage")
            if not u:
                continue
            # one API call can emit several transcript entries (content blocks
            # streamed separately); dedupe on the message id + usage identity.
            key = (
                msg.get("id"),
                u.get("cache_read_input_tokens"),
                u.get("cache_creation_input_tokens"),
                u.get("output_tokens"),
            )
            if key in seen:
                continue
            seen.add(key)
            inp = u.get("input_tokens", 0) or 0
            cc = u.get("cache_creation_input_tokens", 0) or 0
            cr = u.get("cache_read_input_tokens", 0) or 0
            out = u.get("output_tokens", 0) or 0
            yield {
                "sidechain": bool(d.get("isSidechain")),
                "model": msg.get("model"),
                "ts": d.get("timestamp"),
                "input": inp,
                "cache_creation": cc,
                "cache_read": cr,
                "prompt": inp + cc + cr,
                "output": out,
            }


def measure(path, include_sidechains=True):
    calls = [c for c in calls_from(path) if include_sidechains or not c["sidechain"]]
    if not calls:
        return None
    prompt = sum(c["prompt"] for c in calls)
    out = sum(c["output"] for c in calls)
    cread = sum(c["cache_read"] for c in calls)
    ccreate = sum(c["cache_creation"] for c in calls)
    uncached = sum(c["input"] for c in calls)
    peak = max(c["prompt"] for c in calls)
    # distinct context that ever existed: everything ever written to cache, plus
    # the never-cached tails, plus what the model itself generated.
    distinct = ccreate + uncached + out
    return {
        "file": os.path.basename(path),
        "n_calls": len(calls),
        "n_sidechain_calls": sum(1 for c in calls if c["sidechain"]),
        "prompt_tokens": prompt,
        "output_tokens": out,
        "cache_read": cread,
        "cache_creation": ccreate,
        "uncached_input": uncached,
        "peak_context": peak,
        "mean_prompt_per_call": round(prompt / len(calls)),
        "distinct_context": distinct,
        # headline ratios
        "amplification_vs_peak": round(prompt / peak, 2) if peak else None,
        "amplification_vs_distinct": round(prompt / distinct, 2) if distinct else None,
        "cache_read_share": round(cread / prompt, 4) if prompt else None,
        "output_share": round(out / (prompt + out), 5) if prompt else None,
        "models": sorted({c["model"] for c in calls if c["model"]}),
    }


def main(argv):
    include_side = "--no-sidechains" not in argv
    args = [a for a in argv if not a.startswith("--")]
    paths = []
    for a in args:
        paths.extend(sorted(glob.glob(a)) if any(ch in a for ch in "*?[") else [a])
    rows = [r for r in (measure(p, include_side) for p in paths) if r]
    rows.sort(key=lambda r: -r["prompt_tokens"])
    print(
        json.dumps(
            {
                "sessions": rows,
                "totals": {
                    "n_sessions": len(rows),
                    "n_calls": sum(r["n_calls"] for r in rows),
                    "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
                    "output_tokens": sum(r["output_tokens"] for r in rows),
                    "cache_read": sum(r["cache_read"] for r in rows),
                    "distinct_context": sum(r["distinct_context"] for r in rows),
                    "amplification_vs_distinct": (
                        round(
                            sum(r["prompt_tokens"] for r in rows)
                            / sum(r["distinct_context"] for r in rows),
                            2,
                        )
                        if rows
                        else None
                    ),
                },
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main(sys.argv[1:])
