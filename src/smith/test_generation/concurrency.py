# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import os
from concurrent.futures import ThreadPoolExecutor, as_completed


def resolve_generation_concurrency():
    raw = os.getenv("GENERATION_CONCURRENCY", "4")
    try:
        requested = int(raw)
    except ValueError:
        print(f"  Invalid GENERATION_CONCURRENCY={raw!r}, sending one batch at a time")
        return 1
    return requested if requested > 1 else 1


def run_batches(batches, work, label, concurrency=None):
    if concurrency is None:
        concurrency = resolve_generation_concurrency()
    if concurrency < 1:
        concurrency = 1

    total = len(batches)
    results = [None] * total

    def _work(pos):
        try:
            return pos, work(batches[pos]), None
        except Exception as e:  # noqa: BLE001 - surfaced per batch by the loop below
            return pos, None, e

    if concurrency == 1 or total <= 1:
        completed = [_work(pos) for pos in range(total)]
    else:
        print(f"  Dispatching {total} {label} batches, {concurrency} at a time...")
        completed = []
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(_work, pos) for pos in range(total)]
            done = 0
            for fut in as_completed(futures):
                completed.append(fut.result())
                done += 1
                if done % 5 == 0 or done == total:
                    print(f"  Completed {done}/{total} {label} batches")

    # File each result by its ORIGINAL index, not its arrival position.
    for pos, result, error in completed:
        if error is not None:
            print(f"  Error in {label} batch {pos + 1}/{total}: {error}")
            continue
        results[pos] = result

    return results
