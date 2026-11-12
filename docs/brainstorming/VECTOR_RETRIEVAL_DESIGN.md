# Design proposal: security analysis context budget, catalog provenance, and ranking

> Status: proposal. Nothing has been implemented.
>
> The proposal has three parts, split into PRs in §8:
>
> 1. **Provenance:** `--prepare` writes the exact catalog slice each phase
>    reads into the analysis directory, and the checkpoint verifies that slice
>    against the current catalog. This work is useful on its own.
> 2. **Context budget:** smaller handoffs between phases, a context boundary at
>    every phase, batches within a phase when one phase still exceeds its
>    budget, and a per-call budget with room for output and retries. All 61
>    scenarios are still validated across the batches. §5A.
> 3. **Ranking:** order each phase's catalog entries by relevance and add
>    cross-category candidates in Phase D, inside the part 2 budget. This part
>    proceeds only if §9.0 shows that ordering changes decisions.
>
> Context use is a goal. The catalog is a minor part of it: in the committed
> examples Phase D's catalog slice is 3–7K of 22–42K input tokens (§2). So the
> reductions come from handoffs and batching. Required catalog content is never
> filtered out by score (§0.1).

## 0. Context for the reader

Smith runs a four-phase security analysis of a target agent before generating
an OPA policy. Each phase has a Markdown guide
(`opa_policy/guidelines-security-analysis/steps/`), and each ends at a
checkpoint. `security_analysis_checkpoint.py` validates the phase's
structured output, renders it to a markdown artifact, and appends it to
`analysis_state.json`, the running record every later phase reads.

The phases:

| Phase | Produces |
|---|---|
| A | Architecture inspection — what tools, fields, and subjects exist |
| B | Policy intent — roles, permissions, approval paths, rate limits |
| **C** | **Threat model** — attack surfaces, threat instances, per-scenario coverage |
| **D** | **Enforcement mapping** — who owns each threat; proposed OPA guidance |

Phases C and D consult the OWASP catalog
(`src/smith/data/owasp_10_ai_catalog.json`): a local JSON copy of the *OWASP
Top 10 for Agentic AI Security*, holding 10 threat categories (`ASI01`–`ASI10`),
each with a description, aliases, concrete **attack scenarios**, and
**mitigations**. Phase C decides which catalog scenarios apply to this system;
Phase D decides which mitigations become policy.

The current workflow has two kinds of problem. On the catalog side, phases load
entries in catalog order, the run does not record which catalog content it
used, and later phases cannot detect catalog changes. On the context side, all
four phases run in one session. Each phase reads every earlier phase's full
structured output, so source reads, chat history, outputs and retries
accumulate. By Phase D the files alone are 22–42K tokens.

This proposal writes each phase's inputs (catalog slice and predecessor handoff)
to files, records and verifies them, and sizes each model call against a
budget. In PR 3 it also orders the catalog slice by relevance. Each phase still
receives all the content it is required to see, and the run records exactly
what it received.

The implementation uses two small embedding matrices—61 scenario rows and 300
mitigation rows—and exact matrix multiplication. It does not need a vector
database (§6).

### 0.1 Where the context goes, and what each part changes

Earlier drafts called context capacity a non-goal because the catalog fits in
the window. That was the wrong unit. The question is what the whole analysis
consumes, and the catalog is a small share of it. Committed examples, Llama 3
tokenizer (full table in §2):

| | Range across the five examples |
|---|---|
| Phase A–C structured artifacts | 15.7–34.0K |
| Phase D input files (A–C data, tools, system vars, guidance, catalog slice) | 22.3–42.0K |
| of which Phase D's catalog slice | 3.3–7.5K |
| of which Phase C's `Scenario Coverage`, which Phase D never uses | 3.2–4.5K |
| Phase D output | 4.6–8.2K |

These are file counts, so they are lower bounds. A real run also carries chat
history, source reads from Phase A, earlier outputs and retries, all in the same
session (§5A). §9.A measures real runs.

So the design has two separate goals, met by different parts:

| Goal | Met by | Mechanism |
|---|---|---|
| **Smaller context** | PR 2 (§5A) | Phase-scoped handoffs, a context boundary per phase, budget-sized batches |
| **Provenance** | PR 1 (§5) | Recorded, verified input files |
| **Attention** | PR 3 (§6) | Order each batch's catalog slice by relevance |
| **Novelty signal** | PR 3 (§6) | Flag a surface unlike every catalog scenario |

One thing is **not** used to save context: dropping required catalog entries.
Phase C must still see all 61 scenarios and Phase D every applicable
mitigation (§3). Filtering those by score would cut at most 3–7K tokens from
Phase D, at the cost of the coverage guarantee, while the handoff and batching
levers are larger and cost no coverage. So ranking stays rank-and-record:
`rank` reorders a batch's slice and has no threshold. Cross-category additions
from `search` are bounded by whatever budget remains (§5A). The only absolute
threshold is `novel_floor`, which gates a flag and never content.

## 1. Problem

Phases C and D read `src/smith/data/owasp_10_ai_catalog.json` directly:

- **The model selects its own slice.** `threat_model.md:9` points Phase C at the raw catalog and asks it, in prose (`:13-15`), to skip mitigation fields. `enforcement_mapping.md:11` asks Phase D, in prose, to load mitigations only for applicable categories. Nothing records or checks what was actually read.
- **Catalog-order loading.** Phase C takes the full discovery slice, while Phase D takes every mitigation from each applicable category in catalog order. For the catalog, the issue is order, not volume (§0.1).
- **Accumulating context.** The parent workflow runs every phase in one session, and each phase reads "Phase A–C structured data" in full (`enforcement_mapping.md:9`). Phase D's file inputs alone reach 42K tokens (§2) before history, source reads, output and retries. No phase has a budget, and nothing is ever dropped from the session.
- **No provenance.** `checkpoint()` receives `catalog` but omits it from `payload["inputs"]` (`security_analysis_checkpoint.py:942-965`), unlike `tool_definitions` / `system_vars` / `guidance`, which all get `{path, sha256}`.
- **Silent staleness.** The only catalog-derived check is a per-ASI scenario count (`:569`). Rewording a scenario leaves the count unchanged, so the checkpoint can pass even though an earlier disposition refers to different content. `guidance_merge.py:201-213` re-verifies guidance hashes but not the catalog hash.

Hashing the catalog file at checkpoint time does not fix the first problem.
`checkpoint()` runs after the phase, so its hash describes the file at the end of
the phase, not what the model read during it. The fix is to give the model a
file and then check that file.

**Goal:** give each phase a recorded, verifiable set of inputs; keep every model
call within a stated budget; and (in PR 3) add relevance ordering. None of this
changes the content each phase is required to see.

## 2. Measured facts

All token counts in this document use the Llama 3 tokenizer, run over files
committed on `main` (`a669c44`). Earlier drafts used a different count, so the
catalog figures below are about 20% lower than in those drafts.

### Catalog

| | Count / size |
|---|---|
| Entries / scenarios | 10 threats, **61** scenarios |
| Retrievable items | **two separate indexes** (§6): 61 scenarios, and 78 `mitigations` + 222 `mitigation_steps` = 300 mitigation items |
| Mean item size | scenario 255 chars; mitigation item 126 chars |
| Phase C discovery slice | ~6.9K tokens (`description`, `attack_scenarios`, `threat_aliases`) |
| Phase D mitigation slice | ~12.2K tokens for all ten; ~3.3K (77 items) for hr-agent's 3 applicable categories |
| Catalog history | one commit (`c189f8d`, 2026-09-09) |

### Phase inputs and outputs, per committed example

| Example | A | B | C | A–C | Applicable ASIs | D catalog slice | D input files | D output | Threats |
|---|---|---|---|---|---|---|---|---|---|
| hr-agent | 6.5K | 5.0K | 12.3K | 23.7K | 3 | 3.3K | 27.4K† | 8.2K | 14 |
| employee | 11.8K | 10.8K | 11.4K | 34.0K | 5 | 6.4K | 42.0K | 5.6K | 13 |
| RagChatbot_MCPServer | 9.0K | 6.4K | 9.6K | 25.1K | 6 | 7.5K | 37.4K | 6.1K | 9 |
| call-for-papers-mcp | 3.3K | 3.5K | 8.9K | 15.7K | 4 | 5.4K | 22.3K | 4.6K | 9 |
| car-price-mcp-main | 4.9K | 6.2K | 10.3K | 21.4K | 3 | 4.1K | 27.4K | 6.3K | 10 |

A, B and C are each phase's structured JSON. D input files are A–C plus
`tool_definitions.json`, `system_vars.json`, `guidance.txt` and the D catalog
slice. The parent workflow and D step guide add another 2.5K.
†hr-agent has no committed `tool_definitions.json`, so its figure is low.

Where Phase D's input goes (from the per-table breakdown):

- **`Scenario Coverage`** is 3.2–4.5K tokens and the largest table in four of
  the five threat models. It is Phase C's completeness contract, and no Phase D
  rule reads it.
- The Phase C tables Phase D does use (`Threat Instances`, `Category
  Assessment`, `Attack Surfaces`, `Evidence Index`) come to 5.4–7.1K.
- Phase B's `Answer Register` is 1.9–4.0K. Phase D needs each answer's
  confidence (eligibility rule 1) but not the full deliberation.
- Phase A's tables are mostly needed. `Tool Arguments` (`Acts on`, rule 7),
  `Runtime Subject Context` (rule 4) and the source-layer tables (the
  source-boundary rule) all feed eligibility.

These are file counts, not run measurements. §9.A specifies the run
measurements.

**hr-agent, as committed** (`examples/hr-agent/.../threat_model.json`): 14
threats `T01`–`T14`, 61 coverage rows. `Category Assessment` marks `ASI01`
Partial, `ASI02` Yes, `ASI06` Partial, and the other seven No. Twelve threats
are `ASI02`, `T05` is `ASI06`, and `T12` is the only `ASI01` threat. Earlier
drafts of this document assumed 7 applicable categories and an ~11.2K-token
Phase D block. That does not match the committed artifact, and the figures
below are corrected throughout.

These figures describe catalog size, not retrieval quality. They do not show
that the current ordering produces worse dispositions. With 77 items in Phase D
for hr-agent, ordering has little room to matter. That weakens the case for arm
B in §9.0 on this example. §9.0 defines the comparison needed to determine
whether ranking improves Phase D.

## 3. Binding constraint

`security_analysis_checkpoint.py:729-742` builds `expected` as the full
ASI×scenario cross-product and rejects missing rows; `:607-611` requires
`ASI01`–`ASI10` exactly once. Phase C must disposition all 61 scenarios and all
10 categories. The hr-agent artifact therefore contains exactly 61 `Scenario
Coverage` rows. Phase D has no equivalent coverage rule for mitigations.

> **Invariant.** Retrieval is additive to a deterministic baseline. Each phase
> keeps an exact set of required IDs; retrieval may reorder that set or add
> candidates, but it never removes baseline entries.
>
> The baseline matches what each phase reads today:
>
> | Phase | Baseline (guaranteed, retrieval-independent) |
> |---|---|
> | C | all 61 scenarios — the coverage contract above |
> | D | all mitigation items of **every applicable category** (`Applicability ∈ {Yes, Partial}`), per `enforcement_mapping.md:11` |
>
> Retrieval changes the order within that set and may add cross-category items
> from non-applicable categories. Without an index, each phase receives today's
> content in catalog order. No score threshold gates the Phase D baseline
> (§0.1).

## 4. Component A — catalog loader and projections

Add `src/smith/tools/security_catalog.py` as the single catalog parser.

- `load_catalog(path) -> Catalog` reads the file once, hashes those bytes, and
  parses them. `Catalog` carries `sha256`, `framework`, `version`, ordered
  `entries`, and `scenario_counts`.
- **Strict structure.** IDs must be exactly `ASI01`–`ASI10`, each once, and every
  entry needs at least one scenario. A zero-scenario entry currently drops that
  ASI from `expected` (`:729-742`) and quietly reduces mandatory coverage. The
  current catalog passes all of these checks. Existing `"OWASP catalog is
  missing/malformed"` messages are kept.
- **Scenario IDs** `ASI03#4` (1-based) match the existing `Scenario Coverage`
  column, so no artifact changes. Mitigation-level IDs (`ASI03/mit#2`,
  `ASI03/step#5`) exist only for ranking and move to PR 3 (§6).
- `discovery_projection(catalog)` returns `id`, `name`, `description`,
  `threat_aliases`, and `attack_scenarios` for all ten entries. Mitigation and
  impact keys are absent from the output.
- `mitigation_projection(catalog, asi_ids)` returns `impact`,
  `business_impact`, `mitigations`, `mitigation_steps`, and `source_url` for
  exactly those IDs, and raises on an unknown ID.
- `_validate_threat_model` takes a `Catalog` instead of a `Path`.
  `checkpoint()` loads the catalog once and passes the same object to every
  validation in that call (`:884-929`), so Phase C and Phase D re-validation see
  the same bytes. `_catalog_scenario_counts` (`:569`) becomes a thin delegate.

## 5. Component B — catalog snapshots and freshness

### The model reads a snapshot, not the catalog

`--prepare` already resets a phase and writes its JSON template
(`prepare_phase`, `:476`). It now also writes the catalog slice the phase
should read:

| Prepare | Writes | Contents |
|---|---|---|
| `--phase C` | `owasp_catalog_C.json` | `discovery_projection` + catalog `framework`, `version`, `sha256` |
| `--phase D` | `owasp_catalog_D.json` | `mitigation_projection` for the categories Phase C marked `Yes` or `Partial` + the same header |

Phase D's category set is read from the checkpointed Phase C state in
`analysis_state.json`, not supplied by the model. For the committed hr-agent
run that is `ASI01 ASI02 ASI06`. `prepare D` fails if Phase C has no passing
checkpoint.

Both snapshots are written with sorted keys, so the same catalog always
produces the same bytes. `threat_model.md:9` and `enforcement_mapping.md:11`
point to the snapshot instead of the raw catalog. The prose rules in
`threat_model.md:13-15` and `enforcement_mapping.md:11` become true by
construction: Phase C's file contains no mitigations, and Phase D's file
contains only applicable categories.

This is the main change from earlier drafts, which hashed the catalog at
checkpoint time. The snapshot is both what the model reads and what gets
verified, so the record describes the model's actual input. It also removes the
need for per-item hashes and a separate `consulted` record in PR 1.

### Provenance

Snapshots join the existing `input_paths` dict (`:942`), so they get the same
`{path, sha256}` record as `tool_definitions`, `system_vars`, and `guidance`,
with no new mechanism. The catalog itself is recorded too:

```json
"inputs": {
  "owasp_catalog":   {"path": "…/owasp_10_ai_catalog.json", "sha256": "…"},
  "owasp_catalog_C": {"path": "…/owasp_catalog_C.json", "sha256": "…"},
  "owasp_catalog_D": {"path": "…/owasp_catalog_D.json", "sha256": "…"}
}
```

Records go in `analysis_state.json`, not in phase artifacts, so artifact
schemas and the five committed example sets are unchanged. State readers already
use `.get()` (`guidance_merge.py:185-213`), so the new keys need no migration.
`_reset_phase_outputs` (`:461`) deletes a phase's snapshot along with its other
outputs, and `.gitignore` adds `owasp_catalog_*.json` next to
`analysis_state.json` (line 61).

### Snapshot validation and hashing

The checkpoint reads each snapshot **once**. It validates those bytes and
records the hash of those same bytes. It never re-reads the path to hash it. If
it did, a file replaced between validation and hashing would leave a record
for bytes that were never checked.

Validation is strict, because the snapshot is exactly what the model read and
any content the check skips is content the model may have used unchecked:

- The top level must have exactly the expected keys. An unexpected key fails:
  for example, a `mitigations` field in a Phase C snapshot.
- Every entry must be a JSON object. Non-object rows fail rather than being
  dropped.
- IDs must be strings and must be unique. A non-string ID raises
  `ReconciliationError` with the malformed-catalog message, never a
  `TypeError` traceback. A duplicate ID fails, rather than the last entry
  silently winning. Entries are compared as an ordered list, not built into a
  dict that would collapse duplicates.
- Every entry must have exactly its projection's keys.

The same rules apply to `load_catalog` (§4), so a malformed catalog and a
malformed snapshot fail the same way.

### Freshness gate

At checkpoint, for the current phase and every earlier catalog phase, rebuild
the projection from the current catalog and compare it with the validated
snapshot:

| Condition | Outcome |
|---|---|
| Phases A, B | no check |
| Snapshot missing | fail: `re-run --prepare --phase C` (or `D`) |
| Snapshot differs from current projection | fail, naming the first changed item, e.g. `ASI03#4 changed since Phase C was prepared; re-run Phase C` |
| Snapshot matches | pass, record hashes |

The comparison is on content, so the error can name the scenario or category
that changed, which a hash mismatch can't. Each phase is invalidated only by
changes to its own slice. A mitigation-only edit fails Phase D but leaves Phase
C valid, and an edit to a non-applicable category's mitigations affects
neither.

An edit made between `--prepare` and the checkpoint is caught the same way,
because the snapshot was written from the earlier catalog.

All checks run before any artifact is written (`:936-941`), so a failed check
leaves no files changed.

### Merge guard

`_verify_checkpoint` in `guidance_merge.py` (`:202`) already re-hashes
`guidance` and `guidance_updated` against the state. Add `owasp_catalog` to
that loop so guidance derived from an older catalog cannot be merged.

### Not in PR 1: `--accept-catalog-change`

Earlier drafts added an override flag and a `superseded` record so a catalog
update would not force all five committed examples to re-run Phase C. That
problem doesn't exist yet. `analysis_state.json` is gitignored and no committed
example carries one, so a catalog change can't invalidate a committed
example. The catalog has changed once in its history. A run interrupted by a
catalog update simply re-runs `--prepare`. Revisit the flag if committed state
appears or catalog updates become routine (open question 7).

## 5A. Component B2 — context budget, handoffs and batches (PR 2)

### Constraint: phases stay visible

The parent workflow requires each phase to run "visibly in the current
user-controlled session" and forbids delegating a phase to a hidden agent
(`guidelines-security-analysis.md`, *Shared phase contract*). So batches cannot
be subagents. What makes a smaller context possible within that rule is a
different line of the same contract: "Treat persisted structured
artifacts—not unstated prior reasoning—as the input contract between phases."

If every phase and every batch reads only files and ends at a deterministic
checkpoint, the session can be reset between them without losing anything. The
reset itself belongs to the host (a new conversation, a clear, or compaction)
and stays visible to the user. This design makes the reset safe and tells the
user when to do it; it does not depend on a particular host. A host that cannot
reset still benefits from smaller per-step inputs, but not from freedom from
accumulation. §9.A reports which mode each measurement used.

Three levers, in order of cost. Each is used only if the previous ones leave a
call over budget.

### Lever 1: a context boundary at every phase

Each phase starts in a fresh context and reads only its step guide, the parent
contract, its handoff and its catalog snapshot. This needs only a guide change.
Phase A's source reads and each phase's reasoning never reach later phases.
The file counts in §2 cannot measure this lever, and it is likely the largest
of the three. §9.A measures it first.

### Lever 2: phase-scoped handoffs

`--prepare --phase <P>` writes `handoff_<P>.json`, a projection of the
checkpointed earlier phases containing only what phase P's rules use. It is
built from `analysis_state.json`, so every value in it has already passed a
checkpoint. It is recorded in `input_paths` and verified at checkpoint exactly
like a catalog snapshot (§5): rebuild from state, compare, fail on difference.

A handoff may drop whole tables or columns, never rows. Rows are facts later
phases cite by ID, so dropping rows would amount to filtering. The dropped
tables and columns are listed below, so a reviewer can check them against the
step guide.

**Phase D handoff**, from the eligibility and reconciliation rules in
`enforcement_mapping.md`:

| From | Kept | Dropped |
|---|---|---|
| A | `Tool Arguments`, `Runtime Subject Context`, `Enforcement Points`, `Undeclared Fields`, `Layers`, `Prompt Inputs`, `External Data` | non-table content |
| B | `Role Permissions`, `Approval Paths`, `Rate Limits`, `Severity Levels`, `Violation Codes`, `Parameter Details`, `Runtime Subject Details`; `Answer Register` reduced to question ID, answer and confidence | rest of `Answer Register`; non-table content |
| C | `Threat Instances`, `Category Assessment`, `Attack Surfaces`, `Evidence Index`, `Phase Handoff` | `Scenario Coverage`; other non-table content |

Dropping `Scenario Coverage` and the A/B non-table content saves 5.1–7.2K tokens
per example, or 14–26% of Phase D's input files, before the `Answer Register`
reduction. **Phase C's handoff** is built the same way from
`threat_model.md`'s rules over A and B. The table-level audit for Phase C is
the first implementation task of PR 2.

### Lever 3: batches within a phase

Batches are used only when a phase's estimated call still exceeds the budget
after levers 1 and 2. Each batch reads only files and ends at a batch checkpoint
that validates and writes its partial, so a context reset between batches loses
nothing.

**Phase C**

- **C1 (one call):** `Attack Surfaces`, `Evidence Index` and `Category
  Assessment`, which needs all ten category descriptions. The C1 checkpoint
  validates these tables, except Attack Surfaces' `Threat IDs / N/A`
  back-references, because threats don't exist yet. A side effect: surfaces are
  validated before PR 3's ranking uses them, which removes the Phase C caveat
  in §6.
- **C2…Ck:** `Threat Instances` and `Scenario Coverage` for a group of ASIs.
  Each batch receives the handoff, C1's tables, and the discovery slice for its
  ASIs only. Every scenario belongs to exactly one batch, so coverage is split
  across batches, not reduced.
- **Merge (deterministic CLI step):** concatenate the batches; renumber threats
  `T01`… in batch order and rewrite citations to match; fill each Attack
  Surface's back-references from the threats' `Surface` column. Then run
  **today's** Phase C checkpoint on the merged JSON. The 61-scenario rule
  (`:729-742`) and the `ASI01`–`ASI10` rule are unchanged.
- **Risk: cross-batch duplicates.** One surface may yield near-identical threats
  under two ASIs, which `threat_model.md` asks the model not to do. The merge
  flags candidates (same `Surface` and `Actor` in different batches) for the
  user and never merges them automatically. §9.A measures threat-count drift
  against unbatched runs.

**Phase D**

- **D0 (one call):** `Existing Guidance Normalization`. It needs only guidance
  and tool definitions, and every batch compares candidates against it.
- **D1…Dk:** groups of threats. Each batch receives the handoff, cut to its own
  `Threat Instances` and the `Attack Surfaces` / `Evidence Index` rows they
  cite (full `Category Assessment`); tool definitions; system vars; D0's
  normalization rows; and the **full applicable catalog slice**. Each writes
  `Threat Disposition`, `Input Schema`, `Rules`, `Candidate Reconciliation`
  and `Gap Register` rows for its own threats.
- **D-final (one call):** the steps that need every batch's output — collective
  coverage and consolidation into guidance groups, `Prior Proposal
  Reconciliation`, and the addendum. Its input is the merged candidate rows,
  guidance and the prior addendum, with no catalog. Scope Assessment rows are
  pre-filled from the merged `Threat Disposition` (`Partial` exactly when a
  category has both OPA and other-layer threats); the model writes only
  `Reason / owner`.
- The checkpoint on the merged JSON is today's, including "every threat exactly
  once" (`:756-764`).

**Every Phase D batch gets the whole applicable baseline.** That keeps the §3
invariant: no batch sees less catalog content than Phase D sees today. The cost
is that the slice repeats in every batch (3.3–7.5K each). The alternative —
each batch gets its threats' own categories plus ranked items — would save more
but gives up "never below today", and §9 would have to measure the recall loss.
It is recorded as a fallback if §9.A shows the repeated slice dominates.

Batching trades total tokens for peak context, because the handoff and catalog
slice repeat per batch. So `k` is the **smallest** count that fits the budget.
It is not one batch per threat.

### Budget

Each model call has a budget `B = f × W`. `W` is the configured model's context
window. `f` (default 0.5) leaves headroom for reasoning and host overhead.
`--prepare` estimates each call as:

```
E = guides + handoff + catalog slice + batch rows + O_est + R_est
```

- `O_est` is the expected output: a per-row rate calibrated from committed
  outputs, multiplied by the batch's rows. Phase D currently produces 0.43–0.67K
  tokens per threat; the default uses the top of that range.
- `R_est` reserves one retry: the checkpoint's error text plus a re-emitted
  output, about `O_est`.

If `E ≤ B` the phase runs as one batch. Otherwise `--prepare` picks the smallest
`k` for which every batch fits, and writes `batch_plan.json` (batches, their
estimates, `B`, `f`, `W`). The plan is recorded in `input_paths` like the other
inputs. Estimates use a fixed tokenizer and are for planning only; the
checkpoint never fails on them. §9.A compares them with host-reported usage
and recalibrates the rates.

**Cross-category additions draw on the same budget (PR 3).** For each Phase D
batch, the room left after the rank-only estimate, `B − E`, is divided by the
mean mitigation-item size. That gives the batch's `max_items`: derived from the
budget, not configured. If the room is zero or negative, the batch gets no
additions, and `consulted` records why.

## 6. Component C — ranking & cross-category search

### Where

- **Phase D—per-threat ranking (primary).** For the committed hr-agent run, the phase reasons about 14 threats using one ~3.3K-token, 77-item mitigation block (`ASI01`, `ASI02`, `ASI06`) in catalog order. The baseline remains every mitigation item from every applicable category (§3). Ranking presents that baseline separately for each threat, with the closest items first. A second operation adds top-_k_ items from non-applicable categories through `exclude_asi`. This cross-category augmentation is the only path that adds content.

  **The motivating example needs restating.** Earlier drafts described an
  `ASI01` threat "T1" whose useful mitigations sit in `ASI03` and `ASI02`, and
  called it an ordering test because both categories were applicable. In the
  committed artifact, IDs are `T01`–`T14`, the only `ASI01` threat is `T12`
  (direct plan injection), and `ASI03` is marked `No`. If `ASI03` mitigations
  help `T12`, that is an **augmentation** case (arm C in §9.0), not ordering.
  With 77 items, the ordering-only case on hr-agent is weak. §9.0 should use an
  example with more applicable categories, or accept that arm B may show no
  effect here.
- **Phase C—advisory ranking (secondary).** Coverage remains complete, so ranking does not reduce the 6.9K slice. It orders scenarios by similarity to attack surfaces and optionally flags a surface when its best match across all 61 scenarios falls below `novel_floor`. Phase C is also the only path where queries have not yet passed checkpoint validation.
- **Out of scope—the N/A pre-screen.** Earlier drafts used retrieval to label likely-`N/A` scenarios before analysis. That hint could anchor the model and change a disposition, while testing the effect would require a larger Phase C experiment (§9.3). This proposal leaves the pre-screen out. It can be reconsidered with a dedicated evaluation.
- **Rejected:** retrieving category *descriptions*. All 10 are required for `Category Assessment` regardless.

### How

**No new dependencies.** `numpy`, `scikit-learn`, and
`sentence-transformers` are already listed in `[project.dependencies]`
(`pyproject.toml:33-46`). The project already uses the 384-dimensional
`all-MiniLM-L6-v2` encoder (`red_feedback.py:106`, `classify_guidance.py:21`,
`tier2_semantic.py:24`).

**Storage: NumPy matrices rather than a vector database.** The two indexes total
361 rows × 384 float32 values, or about 555 KB. Exact cosine similarity requires
one matrix multiplication per index. FAISS or Chroma would add a dependency
without a practical benefit at this size. The `search()` interface still allows
a later backend change.

New `src/smith/tools/security_catalog_index.py`:

```python
class CatalogIndex:
    @classmethod
    def load(cls, index_dir: Path) -> CatalogIndex: ...

    def rank(self, queries, *, corpus: Literal["scenarios","mitigations"],
             restrict_asi=()) -> list[RankedGroup]:
        """Order the given corpus per query. Drops nothing."""

    def search(self, queries, *, corpus, top_k, max_items,
               exclude_asi=()) -> list[Hit]:
        """Additional candidates from outside `exclude_asi`."""
```

The two entry points serve different purposes (§0.1). `rank` reorders an
existing set and has no threshold, so it cannot remove a baseline item.
`search` returns bounded additions from outside the baseline.

- Artifact: `references/security_catalog_index/{manifest.json, scenarios.npz, mitigations.npz}`, per the `references/` convention. New `SECURITY_CATALOG_INDEX_DIR` in `.env_template` (see open question 2 on committed vs. derived).
- **Two separate indexes** so a scenario query can never return a mitigation item — Phase C field discipline enforced structurally.
- Vectors L2-normalized, so the one surviving absolute threshold (`novel_floor`) is comparable across runs. Deterministic ordering → rebuilds are byte-identical.
- **Embedding text remains an open question.** The initial draft used `f"{entry.name}: {item_text}"` because short clauses such as *"Apply version control."* lack context. However, adding the same category name to roughly 30 items may reduce within-category separation and make cross-category comparison depend too heavily on category labels. Measure prefixed and unprefixed text before choosing a format (open question 1) and before tuning other parameters.
- **Only `search` is bounded, and the cap always wins.** `max_items` is the batch's budget-derived limit (§5A), so it is a hard limit. The "≥1 per query" rule in earlier drafts was a floor that could contradict the cap when queries outnumbered it, so it is now a **priority**, not a guarantee. Allocation is deterministic:
  1. For each query, take its per-query `top_k` candidates, drop any already in the baseline, and deduplicate by canonical ID, keeping the maximum score. A candidate wanted by two queries goes to the one that scores it higher; ties go to the lower threat ID.
  2. **First pass, one each.** Order queries by their best candidate's score, descending. Break ties by severity (`Critical` first), then by threat ID ascending. Give each query its best candidate, in that order, until the cap is reached.
  3. **Second pass, the rest.** Fill any remaining slots from all remaining candidates by score descending, breaking ties by canonical ID ascending.

  If queries outnumber the cap, the queries that pass 2 doesn't reach get no additions. They are recorded in `consulted.D.budget_exhausted`, so the shortfall is visible rather than silent. Because the cap is per batch and batches are sized to the budget, few queries compete for it. With identical inputs the allocation is identical. Results stay grouped by query and carry the originating threat (`"threat": "T12"`). Phase C uses the same rule per `Attack Surfaces` row.
- **`novel_floor` is the only absolute threshold.** A surface whose best similarity across all 61 scenarios falls below the threshold is flagged as a possible novel threat. The threshold affects only the flag; it never adds or removes catalog content. §9.3 evaluates this signal.
- **Queries built from validated artifact fields**, not model prose. This holds exactly for Phase D and only partly for Phase C:
  - Phase D, per `Threat Instances` row: `{Concrete threat} | actor {Actor} | surface {Surface} | severity {Severity}`. `Threat Instances` is a **Phase C** table, already checkpointed and validated before Phase D runs — so the claim holds without qualification.
  - Phase C, per `Attack Surfaces` row: `{Field} | {Source Layer} | {Provenance} | enters at {Enters where}`. `Attack Surfaces` is a **Phase C** table (`security_analysis_checkpoint.py:185`), and today's checkpoint validates the whole phase at once, at the end (`:591-619`). Ranked from an unbatched Phase C, these rows would be model-written but not yet validated.

    §5A's C1 step resolves this. C1 writes and checkpoints `Attack Surfaces` before any scenario work. **When ranking is on, Phase C always runs C1 separately**, even if the budget would allow one batch, so Phase C's queries come from validated rows, as Phase D's do. With ranking off, nothing changes. Ranking stays last in §8 because it depends on PR 2's C1 checkpoint.
- **Index freshness** (`validate_index`) distinguishes an absent index from a
  stale index because the two conditions require different behavior: absence
  falls back to catalog order, while stale data fails closed.

  | Condition | Outcome |
  |---|---|
  | Index dir absent, or weights unavailable | **Degrade to baseline**, warn once, record `"index": null` in `consulted`. Phase runs with today's content in catalog order — §3's invariant, and a contributor without weights is not blocked from running a phase. |
  | `catalog_sha256`, `model_id`, item-count, or manifest-schema mismatch | **Fail closed.** The index describes different content than the catalog in hand; ranking from it would be wrong rather than merely absent. Remediation is an explicit rebuild. |

  Never silently rebuilds mid-phase either way — that would download weights and change retrieved content under review. Reuses §5's hash, so "catalog changed" is one notion, not two.
- **The ranked snapshot and how freshness checks it.** PR 1's freshness gate compares the snapshot with the canonical projection exactly. A ranked Phase D snapshot is no longer exact: it reorders the baseline per threat and may add items from outside it. So PR 3 changes the snapshot's shape so that each part has a precise check. Mitigation-level IDs (`ASI03/mit#2`, `ASI03/step#5`) are introduced here.

  ```json
  {
    "framework": "…", "version": "…", "sha256": "…",
    "baseline":  {"ASI01/mit#3": {…item…}, "ASI02/step#7": {…item…}, "…": "…"},
    "augmented": {"ASI03/mit#2": {…item…}},
    "order": {
      "T12": {"baseline": ["ASI01/mit#3", "ASI02/step#7", "…"],
              "augmented": ["ASI03/mit#2"]}
    }
  }
  ```

  Each item's content appears once, keyed by ID. Per-threat order lists refer to IDs, so a batch's prompt can be rendered in that threat's order without duplicating content. The freshness gate checks each part separately:

  | Part | Must hold | Catches |
  |---|---|---|
  | `baseline` | ID set **equals** the current projection's for the applicable categories, and every item's content equals the current catalog's. Order is irrelevant (it's a keyed object). | a missing, extra, or changed baseline item |
  | `augmented` | Every ID exists in the current catalog with identical content, belongs to a **non**-applicable category, and is not in `baseline`; the count per batch is ≤ that batch's `max_items`. Need not be complete. | a changed or invented addition; an addition masquerading as baseline |
  | `order.*.baseline` | A **permutation** of the `baseline` IDs: same set, each once | a threat shown fewer baseline items than the rest |
  | `order.*.augmented` | A subset of `augmented`, each once | an addition shown to a threat it wasn't allocated to |

  Scores and the allocation are recorded in `consulted` (below) but not re-derived at checkpoint, which would need the model weights. If the index is present and fresh, `--flag security_catalog_index --verify` can re-derive them; that is a review tool, not a gate. With ranking off, `augmented` and `order` are absent and `baseline` is exactly PR 1's projection, so PR 1's check is the special case where the order lists are empty.

  ```json
  "catalog": {
    "index": {"model_id": "all-MiniLM-L6-v2",
              "params": {"top_k": 8, "novel_floor": 0.25, "f": 0.5}},
    "consulted": {
      "C": {"novel_candidates": [{"surface": "#12", "best_score": 0.19}]},
      "D": {"scores": {"T12": {"ASI01/mit#3": 0.61, "…": "…"}},
            "augmented": [{"id": "ASI03/mit#2", "score": 0.58, "threat": "T12", "pass": 1}],
            "max_items": {"D1": 14, "D2": 9},
            "budget_exhausted": []}
    }
  }
  ```

  `max_items` is recorded per batch because it is derived from the batch's budget (§5A), not configured.

## 7. Integration points

**PR 1 — provenance**

| File | Change |
|---|---|
| `src/smith/tools/security_catalog.py` | **new** — `load_catalog`, strict structure checks, `discovery_projection`, `mitigation_projection` |
| `src/smith/tools/security_analysis_checkpoint.py` | `_catalog_scenario_counts` `:569` delegates; `_validate_threat_model` `:582` takes a `Catalog`; `checkpoint()` `:872` loads once and runs the freshness gate before writes `:936`; each snapshot is read once, strictly validated, and hashed from those bytes (§5); snapshots + `owasp_catalog` join `input_paths` `:942`; `prepare_phase` `:476` writes the C/D snapshot; `_reset_phase_outputs` `:461` deletes it |
| `src/smith/tools/guidance_merge.py` | add `owasp_catalog` to the hash loop in `_verify_checkpoint` `:202` |
| `opa_policy/.../steps/threat_model.md` | Inputs `:9` → `owasp_catalog_C.json`; drop the prose field rule `:13-15`, now enforced by the file |
| `opa_policy/.../steps/enforcement_mapping.md` | Inputs `:11` → `owasp_catalog_D.json` |
| `.gitignore`, `CHANGELOG.md` | `owasp_catalog_*.json` next to line 61; `## [Unreleased]` entry noting in-flight runs must re-run `--prepare` |
| `tests/integration/test_security_catalog_unit.py` | **new** |
| `tests/integration/test_security_analysis_checkpoint_unit.py` | snapshot and freshness cases; existing tests that pass `unused-catalog.json` (`:117`, `:159`) for Phases A/B keep working |

No CLI change: snapshots are written by the existing `--prepare` path.

**PR 2 — context budget**

| File | Change |
|---|---|
| `src/smith/tools/security_analysis_handoff.py` | **new** — per-phase handoff projections from `analysis_state.json` (§5A tables), budget estimator, `batch_plan.json` writer |
| `src/smith/tools/security_analysis_checkpoint.py` | `prepare_phase` `:476` writes `handoff_<P>.json` and `batch_plan.json`; `--batch <id>` prepare/checkpoint for C1, C2…Ck, D0, D1…Dk, D-final with partial-shape validation; deterministic C and D merge; today's full-phase checkpoint runs on the merged JSON; handoffs and plan join `input_paths` and the §5 freshness comparison |
| `src/smith/cli.py` | `--batch` arg next to `--phase`; `--context-window` / `SECURITY_ANALYSIS_CONTEXT_WINDOW` and `f` |
| `opa_policy/guidelines-security-analysis/guidelines-security-analysis.md` | shared contract: each phase and batch starts a fresh context and reads only its listed files; when to reset; the batch loop |
| `opa_policy/.../steps/threat_model.md`, `enforcement_mapping.md` | Inputs → handoff file instead of "Phase A–C structured data"; per-batch instructions |
| `.env_template`, `.gitignore`, `CHANGELOG.md` | window and `f`; `handoff_*.json`, `batch_plan.json`, batch partials; `## [Unreleased]` |
| `tests/integration/test_security_analysis_handoff_unit.py` | **new** |
| `tests/integration/test_security_analysis_checkpoint_unit.py` | batch, merge and handoff-freshness cases |

**PR 3 — ranking**

| File | Change |
|---|---|
| `src/smith/tools/security_catalog_index.py` | **new** — build, load, `rank`, `search`, `validate_index` |
| `src/smith/tools/security_catalog.py` | mitigation-level IDs; ranked snapshot writer |
| `src/smith/tools/security_analysis_checkpoint.py` | `consulted` block |
| `src/smith/cli.py` | `security_catalog` + `security_catalog_index` branches near `:624`, `allowed_flags` `:1006`, `--query` / `--no-prefix` args near `:518` |
| `opa_policy/.../steps/*.md` | describe ranked order; restate that **all** scenarios still need dispositions |
| `.env_template`, `.gitignore` | `SECURITY_CATALOG_INDEX_DIR`; index handling per open question 3 |
| `tests/integration/test_security_catalog_index_unit.py` | **new** |

**Unchanged in all three PRs:** the coverage rule at `:729-742`, the canonical
catalog, and phase artifact schemas. PR 2's batch partials are new
intermediate files. The merged phase JSON keeps today's schema, and today's
checkpoint validates it.

The committed artifacts remain validation-compatible. The PR 1 guide change
alters only where the model reads the same content from, so it should not
change results. PR 2 may change results, because each call sees less
conversation and batches see a subset of threats; §9.A measures that. PR 3's
ranked order may too. Decide separately whether to regenerate the examples
(open question 6).

CLI surface (PR 3):

```bash
smith --flag security_catalog [--phase C|D]            # hash, counts, the exact projection
smith --flag security_catalog_index [--build]          # build / show manifest + freshness
smith --flag security_catalog_index --query "…" --phase D   # ranked + scored hits, for tuning
smith --flag security_catalog_index --query "…" --no-prefix # same, prefix off (open question 1)
smith --flag security_catalog_index --verify --phase D      # re-derive recorded scores/allocation (review tool)
```

## 8. Phasing

**PR 1—provenance.**

1. **Loader.** `security_catalog.py` with `load_catalog` and strict structure
   checks; `_catalog_scenario_counts` delegates and `_validate_threat_model`
   takes a `Catalog`, loaded once per `checkpoint()`. Pure refactor: existing
   tests pass unchanged.
2. **Snapshots.** Projections, plus `--prepare` writing `owasp_catalog_C.json`
   / `owasp_catalog_D.json`; reset and `.gitignore` handling; snapshots and the
   catalog recorded in `input_paths`; step guides point to the snapshots. Same
   content, new location.
3. **Freshness gate.** Checkpoint compares each snapshot with the current
   projection and fails with the changed item and the phase to re-run. **The
   only step that can newly fail a passing run.**
4. **Merge guard.** `owasp_catalog` added to `_verify_checkpoint`.

Deferred from earlier drafts: `--flag security_catalog`, mitigation-level IDs,
the `consulted` block (all used only by PR 3), and `--accept-catalog-change`
(§5, open question 7).

**PR 2—context budget, measured at each step.**

5. **Baseline measurement.** §9.A arm 0 on today's workflow. This needs
   per-call usage logging (§9.A) and nothing else.
6. **Context boundary per phase (lever 1).** Guide change only. Measure arm 1.
7. **Handoffs (lever 2).** `handoff_<P>.json`, the Phase C handoff audit, and
   handoff freshness. Measure arm 2.
8. **Budget and batches (lever 3).** Estimator, `batch_plan.json`, batch
   checkpoints and merges. Measure arm 3. **If arms 1–2 already keep every call
   within budget on all five examples, ship the estimator and stop.** Batching
   is the costliest lever and only earns its complexity if a phase still
   exceeds the budget.

**PR 3—ranking, subject to evaluation.**

9. Index build + manifest + `validate_index`. Nothing consumes it yet.
10. `rank`/`search` + `--query`. Resolve open question 1 (prefix on/off), then
    run §9.0 inside the PR 2 workflow. If ordering does not change Phase D
    decisions, stop here.
11. Phase D per-threat ranking + cross-category augmentation within each
    batch's budget, written into the ranked snapshot (§6). The baseline is the
    full applicable set (§3), so with retrieval degraded to nothing the result
    is exactly PR 2's.
12. Phase C scenario ordering + novelty signal. This needs PR 2's C1
    checkpoint (§6) and §9.3's gate. The N/A screen is **out of scope** (§6),
    not deferred to this step.

Steps 1, 2, 4, 5, 9 and 10 do not change what a passing run produces.
Behavioral risk is limited to steps 3, 6–8, 11 and 12. PR 2's steps carry
quality risk, not just failure risk, which is why each lever is measured before
the next is built. Three PRs let provenance ship regardless, let context
reduction ship without ranking, and let ranking be dropped on evidence.

## 9. Evaluation gate

There are two evaluations. §9.A decides how much of PR 2 ships and runs first.
§9.0–§9.3 decide PR 3 and run inside whichever PR 2 workflow §9.A selects.
Because Phase D no longer filters by `min_score` (§0.1), PR 3's evaluation asks
whether ordering changes decisions. Open question 1 fixes the embedding text for
that test, and §9.3 evaluates the separate novelty signal.

### 9.A Context, tokens and quality on real runs (PR 2)

The figures in §2 are file counts. A run's real cost includes chat history,
Phase A's source reads, outputs and retries. This comparison measures those on
full A–D runs.

| Arm | Workflow |
|---|---|
| **0 (today)** | one session for A–D; each phase reads full A–C state |
| **1** | context boundary at each phase (lever 1) |
| **2** | arm 1 + phase-scoped handoffs (lever 2) |
| **3** | arm 2 + budget-sized batches (lever 3), only run if arm 2 leaves a call over budget |

**Examples:** `employee` (largest Phase D input, 42.0K), `call-for-papers-mcp`
(smallest, 22.3K) and `RagChatbot_MCPServer` (most applicable categories, 6).
These are fresh A–D runs from each agent's source, so the committed-artifact
drift that blocks re-checkpointing (§10) doesn't affect them.

**Metrics**, n = 3 per arm per example:

| Metric | Definition |
|---|---|
| Peak context | max over model calls of input tokens for that call |
| Total tokens | sum of input + output tokens per phase and per run |
| Retries | checkpoint failures per phase before `PASS` |
| Budget accuracy | `--prepare`'s estimate `E` against measured peak, per call (arm 3) |
| Quality — Phase C | agreement of `Scenario Coverage` dispositions (threat-cited vs. `N/A`, per scenario) and of `Category Assessment` applicability with arm 0 |
| Quality — threats | threat set overlap with arm 0, matching on ASI + `Surface` + `Actor`; count drift; cross-batch duplicates flagged by the merge |
| Quality — Phase D | agreement of `Threat Disposition` owner per matched threat; emitted guidance compared in the normalized `tool \| subject scope \| field expression \| operator \| values \| deny` form |

Arm 0 is the comparison point because the committed artifacts were produced by
an earlier guide revision and fail to re-checkpoint for three examples (§10).
Agreement is reported against arm 0's own run-to-run agreement. If arm 0 agrees
with itself on 85% of dispositions, arm 2 is judged against that spread, not
against 100%.

**Instrumentation is a prerequisite.** There is no token profiler on `main`; PR
#100 was closed without merging. Step 5 (§8) therefore records per-call usage
from the host or model API (input and output tokens per call) into
`references/security_analysis_usage.jsonl`. Either revive PR #100's profiler or
add a minimal logger. File counts from §2 are only a sanity floor.

**Decision rule.** Ship each lever whose arm lowers peak context without
dropping quality below arm 0's own spread. Stop adding levers once every call
in every example is within budget. If a lever lowers context but costs quality,
report it and don't ship it. A smaller context is not worth worse threat
models.

Phases C and D are nondeterministic LLM runs, so one run per arm is not enough.
Run each arm three times at the configured `TEMP`, report per-threat recall and
the range across runs, and count a difference only when it exceeds the
within-arm spread. If the budget allows only one run per arm, report the result
as preliminary rather than conclusive.

### 9.0 Does per-threat ordering change Phase D's output?

No current measurement shows that catalog ordering hurts Phase D (§2).
Retrieval metrics alone cannot answer that question: `recall@k` shows whether
ranking finds relevant mitigations, not whether Phase D would otherwise miss
them while reading the same full baseline. The evaluation must compare Phase
D's actual output.

Two arms over the same labelled threats, both seeing identical content, differing
only in order:

| Arm | Phase D sees |
|---|---|
| **A (today)** | all applicable-category items, catalog order |
| **B (ranked)** | all applicable-category items, per-threat similarity order |

Measure the following in Phase D's output, not in the retrieval result:

- per-threat recall of labelled mitigations, arm B minus arm A;
- for hr-agent's `T12` (the only `ASI01` threat), whether its cited mitigations
  differ between A and B. Its candidate `ASI03` mitigations are outside the
  applicable set, so they can appear only in arm C (§6);
- items cited in B that the labels call irrelevant — ordering can mislead as
  well as help, by lending the top of the list unearned authority.

A third arm (**C**) adds cross-category candidates from non-applicable
categories. This isolates the only path that adds content. Run it only if B
outperforms A.

**Choice of example.** hr-agent's Phase D baseline is 77 items across 3
categories (§2), which gives ordering little room to matter. Run §9.0 on the
committed example with the most applicable categories, or on two examples, so a
null result on a small baseline isn't read as a null result in general.

**Decision rule.** If arm B does not outperform arm A beyond the within-arm
spread, do not integrate ranking into the phase workflow. The loader, snapshots,
provenance, and freshness work in §4–§5 remains independent.

### 9.1 Ground truth

- **Available free:** ASI-level labels in the examples (`Threat Disposition`, 14 rows for hr-agent; `Rules.OWASP`). Sanity gate — does a threat's own category rank top-1 for its own text?
- **Must be built:** no artifact cites individual mitigation items, so item-level ground truth requires manual labels (about 30–60 minutes per example, stored as a fixture). §9.0 depends on this fixture.
- **Sets `top_k`:** `recall@k` for k ∈ {4, 8, 16} on the cross-category path only. Since `rank` drops nothing, `top_k` now bounds only additive candidates, where being wrong costs context rather than coverage — so a coarse value chosen from the curve's knee is sufficient. No crossover analysis is needed.

### 9.2 A second example, for `novel_floor` only

`top_k` and `max_items` are context budgets and do not require cross-example
validation. `novel_floor` does because it is an absolute cosine threshold whose
behavior depends on the vocabulary used by each example.

If step 12 proceeds, label a second committed example and check whether the
chosen `novel_floor` separates surfaces marked `novel` from surfaces that cite
catalog scenarios. Use hr-agent for tuning and the second example for
validation. If they require materially different thresholds, either calibrate
per example or remove the signal.

### 9.3 Gate on the novelty signal

The novelty signal needs a separate evaluation from ranking. With 61 scenarios
across ten broad categories, most surfaces will match something above a low
threshold. A low-scoring surface may also reflect vocabulary differences rather
than a new threat. For example, *"PTO balance field"* may be lexically distant
from catalog prose while still being covered by an existing scenario.

**Gate:** on labelled examples, do surfaces flagged below `novel_floor`
correspond to threats the artifact's `Threat Instances` marks `novel`
(`catalog basis = novel`)? That label already exists — no new hand-labelling
needed. Report precision and recall of the flag against it.

If most flagged surfaces are already covered but use different wording, remove
the signal instead of repeatedly tuning the threshold. Phase C has no
deterministic fallback for a misleading novelty hint.

**N/A pre-screen.** Testing whether a likely-`N/A` hint anchors the model would
require three Phase C arms—no screen, hint shown, and hint computed but
withheld—with three runs each. Because the hint can change dispositions and the
evaluation is comparatively expensive, it remains out of scope.

## 10. Tests & verification

Unit lane (`-m unit`): env-free, offline, `tmp_path`-confined, per `tests/integration/TESTING_GUIDE.md`. `make unit` forbids weight downloads, so import `SentenceTransformer` at module scope and let tests patch it, following `test_red_suggestion_unit.py:65` / `test_case_evaluation_unit.py:187`. A fake encoder also makes scores deterministic enough to assert thresholds.

### PR 1

Loader and projections: `load_catalog` reports the hash of the bytes it parsed;
today's missing/malformed messages are preserved; new strict cases fail
(duplicate ID, ID outside `ASI01`–`ASI10`, zero-scenario entry); counts are 61
scenarios; the discovery projection has no mitigation or impact **keys**;
`mitigation_projection` returns exactly the requested IDs and raises on an
unknown one; projections are byte-identical across runs.

Snapshots and freshness:
- **Acceptance test:** reword one scenario without changing its length. On
  `main` the Phase C/D checkpoint passes; after step 3 it fails naming
  `ASI0x#n` and the phase to re-run.
- `prepare D` writes exactly the `Yes`/`Partial` categories from the
  checkpointed Phase C state, and fails when Phase C has no passing checkpoint.
- Catalog edited between `--prepare` and checkpoint → fails.
- Mitigation-only edit → Phase D fails, Phase C still passes; edit to a
  non-applicable category's mitigations → neither fails.
- Missing snapshot → fails with the `--prepare` remediation.
- One `checkpoint()` call loads the catalog once and both validations see it
  (`:884-929`).
- `_reset_phase_outputs` removes the phase's snapshot and later ones.
- No artifact is written when a freshness check fails.
- `guidance_merge` refuses to merge after a catalog change.
- Existing tests that pass `unused-catalog.json` for Phases A/B (`:117`,
  `:159`) still pass.

Strict snapshot validation (each case is from review of the first
implementation, #154):
- A duplicate `ASI01` with different scenario text, placed **before** the real
  entry → fails. It must not pass with 11 rows by the last entry winning.
- A non-object row → fails rather than being dropped.
- An unexpected top-level key (e.g. `mitigations` in the Phase C snapshot) →
  fails.
- A non-string ID (`1` for `ASI01`) → `ReconciliationError` with the
  malformed-catalog message, not a `TypeError` traceback.
- **Swap between validate and hash:** replace the snapshot after it has been
  read and validated but before state is written (simulated by patching the
  read). The recorded hash is that of the validated bytes, and the next
  checkpoint fails on the mismatch.

Packaging: build the wheel, install it into a clean venv, and check that
`owasp_10_ai_catalog.json` is importable as package data and `load_catalog`
reads it. Don't make the changelog claim that the catalog ships in built
packages until this test passes.

Committed examples: re-checkpointing a copy of each example at Phase C under
`tmp_path` is the regression check for "no artifact schema change". **On
`main` today only `call-for-papers-mcp` and `car-price-mcp-main` pass.**
`hr-agent`, `employee`, and `RagChatbot_MCPServer` fail on architecture drift
unrelated to the catalog (e.g. hr-agent's `architecture.json` cites
`display_compensation` and `get_directory`, which are absent from its
`tool_definitions.json`). PR 1 asserts that the two passing examples still pass
and leaves the other three to a separate fix (open question 8). Phase D
re-checkpoints fail for every example except `call-for-papers-mcp` because
their addenda have already been merged, which is expected and not a regression.

### PR 2

Handoffs:
- Each handoff contains exactly the tables and columns listed in §5A, and every
  **row** of each kept table. A test asserts the row count against
  `analysis_state.json`, so a handoff can never drop rows.
- The Phase D handoff has no `Scenario Coverage` key.
- An edited handoff, or state changed after `--prepare`, fails the checkpoint,
  just as a stale catalog snapshot does.

Batches and merge:
- The Phase C batches partition the 61 scenarios: every `ASIxx#n` is in exactly
  one batch.
- After merge, today's Phase C checkpoint runs unchanged. A merged result
  missing one scenario fails with today's message (`:738`).
- Threats are renumbered `T01`… in batch order, and every citation in
  `Scenario Coverage` and the filled `Attack Surfaces` back-references points
  to the renumbered ID.
- The same `Surface` + `Actor` in two Phase C batches → the merge reports it and
  does not merge the threats.
- The Phase D merge has every threat exactly once in `Threat Disposition`
  (`:756-764`). Scope Assessment `Partial` is pre-filled exactly when a
  category has both OPA and other-layer threats.
- **Every Phase D batch's catalog slice equals the full applicable
  projection** — the §3 invariant under batching.
- A context reset between batches loses nothing: running each batch from a
  fresh process, given only its listed files, reproduces the single-process
  merged JSON byte-for-byte when the model output is fixed (a fake model in the
  unit lane).

Budget:
- The estimator is deterministic for a fixed tokenizer and inputs.
- `k` is the smallest batch count for which every batch's `E ≤ B`.
- When the unbatched estimate fits, `k = 1` and the batch plan is a single
  batch, identical in behavior to arm 2.

### PR 3

Index: canonical ID round-trip; counts 61/300; rebuild byte-identical; vectors
unit-norm; `search` respects `top_k`/`max_items`/`exclude_asi`; dedupe keeps
max score; corpora cannot cross.

**Key invariant and regression tests:**
- **`rank` is order-only:** for every input set, output is a permutation with the same multiset of IDs. This directly tests the §3 invariant.
- **Rank-only mode:** with augmentation off, the ranked snapshot's `baseline` equals PR 1's projection exactly, and `augmented` is empty. With the index absent, the whole snapshot is byte-identical to PR 1's.
- **Augmented mode:** `baseline` still equals PR 1's projection exactly. Every `augmented` item comes from a non-applicable category, matches the catalog, and is absent from `baseline`. Each `order.*.baseline` is a permutation of `baseline`.
- **Freshness on a ranked snapshot**, one case per row of §6's table: remove a baseline item, change one, add one → fail. Change an augmented item's text, add an augmented item from an applicable category, or drop an ID from one threat's order list → fail. Reorder one threat's order list → pass.
- **Cap vs. per-query priority:** with 5 queries and `max_items = 3`, exactly 3 additions, going to the 3 queries with the highest best scores. The other 2 are listed in `budget_exhausted`. With equal best scores, `Critical` beats `High`, then the lower threat ID wins. With `max_items = 8`, all 5 queries get one in pass 1, and the remaining 3 slots follow global score order with canonical-ID tie-break. Two identical runs give identical allocations.
- **Budget-derived cap:** a batch whose rank-only estimate already fills `B` gets `max_items = 0`, receives no additions, and records why.
- Phase C ranking permutes but never shrinks the 61-scenario set; Phase C still fails when any scenario lacks a disposition, with ranking active.
- **index absent → degrades and warns**, records `"index": null`, phase passes; **index stale (hash/model/count mismatch) → fails closed**. The two halves of §6's table, which must not be conflated.

### End to end

On a committed example that re-checkpoints cleanly (see above), after `make ci`:

1. Run `--prepare` + checkpoint for C and D; Phase C validates with 61 rows; `owasp_catalog_D.json` contains exactly the applicable categories; `inputs` records both snapshots and the catalog.
2. **Staleness:** in a *copy* of the catalog, edit one `attack_scenarios` string without changing its length; re-run the Phase D checkpoint → fails naming the scenario and Phase C. Passes silently today; that contrast is the acceptance criterion.
3. (PR 2) Run the A–D workflow with a context reset at each phase, from handoff files only. Phase C and D pass today's checkpoint, and `inputs` records each handoff. Then force `k = 2` with a small `--context-window` and repeat. The merged Phase C still validates with 61 rows, and the merged Phase D with every threat once.
4. (PR 3) Build index; 61 + 300 items; manifest hash matches `inputs.owasp_catalog.sha256`.
5. (PR 3) Query `T12`'s text on hr-agent; inspect where `ASI01`/`ASI02` items land and which `ASI03` items `search` adds. This checks the mechanism only; §9.0 decides whether it changes Phase D's output.
6. (PR 3) **Negative test:** with the index dir removed, snapshots are byte-identical to PR 1's. §3's invariant end to end.

## 11. Open questions

1. **Embedding text: category-name prefix on or off?** This must be resolved before §9.0. A bare clause such as *"Apply version control."* may lack context, but `f"{name}: {item}"` gives every item in a category the same strong prefix and may weaken within-category ranking. Compare three formats against the §9.1 labels: `{item}`, `{name}: {item}`, and `{name}: {description[:200]} — {item}`. Fix the format before running the arm comparison.
2. **Is MiniLM the right model for these queries?** Queries are pipe-joined metadata (`{Field} | {Source Layer} | …`), while indexed documents are prose clauses. A symmetric sentence-similarity encoder may compress scores for these short, differently structured texts. Ranking is less sensitive to this than `novel_floor`, which is why §9.3 evaluates the threshold separately. The proposal starts with `all-MiniLM-L6-v2` because Smith already uses it (§6). `manifest.model_id` records the choice so it can change later.
3. **Index committed or derived?** A derived, gitignored index requires model weights wherever ranking runs, although an absent index falls back to catalog order. Committing the reproducible 555 KB `.npz` files avoids that setup cost but adds binary files to review. The current preference is to commit them and document how to reproduce them.
4. **`top_k` by severity?** A `Critical` threat may warrant wider cross-category augmentation than a `Low` one. Defer until flat-`k` is measured — and only relevant if §9.0's arm C ships at all.
5. **`impact` / `business_impact` → Phase D.** `threat_model.md:13-15` lists Phase C's fields as IDs, names, descriptions, aliases, scenarios — impact excluded, consistent with Phase C assigning severity from *system* boundaries (`:35-38`). Flagging as the one non-obvious field assignment.
6. **Should the five examples be regenerated against the revised step guides?** PR 1 changes only where the step guides read catalog content from. PR 2's context boundaries and batches, and PR 3's ranked order, may change results. Regeneration requires five complete Phase A–D runs, which §9.A's arms already produce for three examples. Decide after §9.A, together with question 8.
7. **When does `--accept-catalog-change` become worth building?** It is deferred (§5) because no committed example carries `analysis_state.json` and the catalog has changed once. Triggers to revisit: committed state, a regular catalog update cadence, or long-running analyses that a catalog bump would routinely interrupt.
8. **Three examples fail to re-checkpoint on `main`.** `hr-agent`, `employee`, and `RagChatbot_MCPServer` fail Phase C on architecture drift unrelated to the catalog (§10). PR 1 can only assert no regression on the two that pass. Fix the drift first, in a separate PR, so all five can be the regression baseline?
9. **Which hosts can reset context between phases and batches?** Lever 1 depends on the host providing a visible way to start a phase in a fresh context. Without one, levers 2–3 still shrink each step's inputs, but history still accumulates. Document the supported mode per host in the parent workflow, and record which mode each §9.A run used.
10. **Budget defaults.** `f = 0.5` is a starting guess for headroom. `W` must come from configuration, because Smith's model is set by `.env` and the window varies by model. Calibrate `f` and the output rates from §9.A's budget-accuracy metric before choosing defaults.
11. **Estimator tokenizer.** `--prepare` estimates with a fixed local tokenizer (Llama 3, as in §2), which won't match every configured model's tokenizer. Keep the estimate conservative and calibrate it against host-reported usage. Don't add a dependency per model.
12. **Phase C batch grouping.** Batches are grouped by ASI. The grouping rule — contiguous IDs, or balancing scenario counts so batches have similar `E` — affects how often near-duplicate threats span batches. Choose it from §9.A's cross-batch duplicate counts.
