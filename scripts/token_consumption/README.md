# Token-consumption tools

This directory groups the runnable utilities, experiment configurations, and
historical outputs used to measure Smith's token and context consumption.

## Layout

- `context_profile.py` launches the supported profiler implemented in
  `src/smith/tools/context_profile.py`. The implementation remains in the
  package so the installed `smith-context-profile` command continues to work.
- `phase_cost.py` compares a shared Claude session with a fresh session per
  configured phase.
- `phase_cost_stream.py` performs the comparison in one streaming SDK call and
  uses `/clear` for the isolated variant.
- `token_amplification.py` calculates context-amplification ratios from Claude
  transcript JSONL files.
- `configs/` contains phase prompt definitions.
- `results/` contains historical JSONL experiment outputs.

## Supported profiler

From the repository root:

```bash
uv run --extra context-profile python scripts/token_consumption/context_profile.py run \
  --target examples/call-for-papers-mcp \
  --pairs 1 \
  --output /tmp/smith-context-profile
```

The equivalent installed command is:

```bash
uv run --extra context-profile smith-context-profile run \
  --target examples/call-for-papers-mcp \
  --pairs 1 \
  --output /tmp/smith-context-profile
```

## Experimental runners

```bash
python scripts/token_consumption/phase_cost.py \
  --arm isolated \
  --phases scripts/token_consumption/configs/phases.smoke.json \
  --out /tmp/smoke-isolated.jsonl

python scripts/token_consumption/phase_cost_stream.py \
  --arm shared \
  --phases scripts/token_consumption/configs/phases.smoke.json \
  --out /tmp/smoke-shared.jsonl

python scripts/token_consumption/token_amplification.py '<transcript-glob>'
```

The two experimental phase-cost runners use the Claude Agent SDK with
`bypassPermissions`. Run them only in a disposable workspace. Historical
results may contain incomplete runs and are not definitive performance
benchmarks.
