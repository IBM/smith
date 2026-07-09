---
title: "Red Feedback Patching"
weight: 11
---

# Red Feedback Patching

Cluster failed adversarial test cases and iteratively patch the policy to block each category of bypass.

## CLI Usage

```bash
smith --flag red_suggestion    # cluster failed cases
smith --flag policy_testing    # verify after each patch
```

## How It Works

### Clustering

Failed test cases are grouped using DBSCAN clustering on their semantic embeddings. Each cluster represents a distinct bypass pattern that needs a targeted fix.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CLUSTER_EPS` | `0.3` | Maximum cosine distance between samples in the same cluster (smaller = tighter) |
| `CLUSTER_MIN_SAMPLES` | `2` | Minimum samples to form a cluster (below this → noise) |

Clusters are numbered sequentially, with the noise group appearing as the last numbered cluster.

Output: `./assets/opa/outputs/cluster_results.txt` — an ordered list of clusters with their member test cases identified by file path.

### Per-Cluster Patching Loop

For each cluster (processed strictly in order):

1. **Backup** — Copy `assets/policy.rego` to `assets/opa/outputs/` with cluster ID and date in the filename
2. **Analyze** — Inspect only the test cases belonging to the current cluster (identified by file path)
3. **Fix** — Propose a minimal, narrowly scoped change targeting this cluster only
4. **Test** — Run `smith --flag policy_testing` and verify:
   - No new FP/FN regressions
   - All cases from this cluster now pass
5. **Human Approval** — The agent asks for explicit approval before moving to the next cluster

### Patching Rules

- Process clusters in the exact order from `cluster_results.txt` — never reorder or skip
- Fix one cluster at a time — do not merge fixes across clusters
- Prefer editing existing logic over adding new rules
- For numeric constraints (e.g., CPU/memory limits), use ranges rather than exact values
- Any new logic must be connected to allow/deny rules
- The task is only complete when ALL clusters have been processed
