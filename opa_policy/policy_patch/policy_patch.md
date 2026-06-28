## Available References and Constrains:

### AUTHORITATIVE PATHS
- Policy file: `./assets/policy.rego`
- Backup folder: `./assets/opa/outputs`
- Cluster results (ORDER IS AUTHORITATIVE): `./assets/opa/outputs/cluster_results.txt`
- Failed test list: `./references/scorecard/score_test_failures.txt`

### IDENTITY RULE
- file_path is the ONLY authoritative identity of a test case.

## Workflow (follow strictly)

### TASK COMPLETION CONDITION (NON-NEGOTIABLE)
- Task is complete ONLY when ALL clusters have been processed AND the final line ALL_CLUSTERS_DONE is printed.
- Completing a single cluster does NOT mean the task is complete.
- At any time, you may reason about ONE cluster only: the current cluster.
- Do NOT skip, merge, reorder, or partially process clusters.
- Do NOT advance to the next cluster until human explicitly says YES.

### Detailed steps
Run `smith --flag policy_testing ` to identify if there is failed test cases. Unlabeled cases should be denied. 

Then, follow the workflow strictly:
====================
STEP 1: CLUSTERING
====================
Run `smith --flag red_suggestion` to cluster failed test cases.
This produces an ORDERED list of clusters at:
`./assets/opa/outputs/cluster_results.txt`

You MUST trust the order in this file.
You MUST NOT sort or reorder clusters yourself.

====================
STEP 2: INITIALIZE GLOBAL STATE
====================
Read `./assets/opa/outputs/cluster_results.txt` ONCE to obtain:
- cluster id: identifier of each cluster
- total_clusters = number of clusters

Maintain:
- completed_clusters = []

If you are ever unsure about remaining clusters,
re-read `./assets/opa/outputs/cluster_results.txt` and compare with completed_clusters.

====================
STEP 3: PROCESS CLUSTERS (NO EARLY STOP)
====================
Process clusters strictly in the order given by ordered_clusters.

For each cluster i in ordered_clusters:
Print header:
=== Processing cluster i / total_clusters ===

Then execute the PER-CLUSTER LOOP.
====================
PER-CLUSTER LOOP (cluster i)
====================
Repeat until human answers YES.

Before EACH step below, print one status line:
STATE: current=i, completed={completed_clusters}, remaining={remaining_clusters}

1) Backup
- Copy `./assets/policy.rego` to `./assets/opa/outputs/`
- Backup filename MUST include cluster id + date

2) Analyze (CURRENT CLUSTER ONLY)
- Inspect ONLY test cases belonging to cluster i
- Identify cases by file_path from `./assets/opa/outputs/cluster_results.txt`.
- Open test data via file_path if needed
- Do NOT reference any other cluster

3) Fix
- Propose a minimal, narrowly scoped change for cluster i only
- Prefer editing existing logic
- When making changes related to resource limits (e.g., cpu, memory), you should consider set a range rather than match the exact numeric values.
- Any new logic MUST be used in allow/deny rules

4) Apply & Test
- Apply change to policy.rego
- Run `smith --flag policy_testing `
- Verify BOTH:
  (a) No new FP/FN regressions
  (b) score_test_failures.txt contains NONE of the file_path entries from cluster i
- If any case from cluster i still fails or new FP/FN introduced, return to step 2

5) Human Approval (CLUSTER BOUNDARY)
Ask explicitly:
“Do you approve these changes and allow moving to the NEXT cluster? (yes/no)”
- YES → keep policy, mark cluster i completed, exit loop
- NO  → incorporate feedback, continue loop on cluster i

====================
AFTER EACH CLUSTER
====================
- Append cluster i to completed_clusters
- Re-read `./assets/opa/outputs/cluster_results.txt`
- remaining_clusters = ordered_clusters - completed_clusters

Print:
Progress: completed={completed_clusters}, remaining={remaining_clusters}

If remaining_clusters is non-empty:
- Immediately continue with the next cluster in ordered_clusters
If remaining_clusters is empty:
- Print final summary
- End with the exact last line:ALL_CLUSTERS_DONE

====================
ABSOLUTE RULES
====================
- You MUST NOT reorder clusters.
- You MUST NOT stop early.
- ALL_CLUSTERS_DONE is the ONLY valid task ending.
- If you lose track of progress at any time:immediately re-read `./assets/opa/outputs/cluster_results.txt` and continue.
