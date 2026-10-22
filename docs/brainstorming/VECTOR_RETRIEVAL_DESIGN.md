# Design proposal: threat catalog ranking, provenance, and freshness

> Status: proposal. Nothing has been implemented.
>
> The proposal has two independent parts, split in §8:
>
> 1. **Provenance:** canonical catalog IDs, phase-specific projections, content
>    hashes, and freshness checks. This work is useful on its own.
> 2. **Ranking:** order each phase's catalog entries by relevance and add
>    cross-category candidates in Phase D. This part proceeds only if the
>    evaluation in §9.0 shows that ordering changes decisions.
>
> Ranking does not filter catalog content by score. §0.1 explains why filtering
> is unnecessary for a corpus of this size.

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

The current catalog path has three limitations: phases load entries in catalog
order, the run does not record which catalog content it used, and later phases
cannot detect catalog changes. This proposal adds a small access layer with
canonical IDs, phase-specific projections, content hashes, and relevance
ordering. Each phase receives the same required content in a more useful order,
and the run records exactly what it received.

The implementation uses two small embedding matrices—61 scenario rows and 300
mitigation rows—and exact matrix multiplication. It does not need a vector
database (§6).

### 0.1 Scope of ranking

The mitigation corpus is about 15.6K tokens, and the scenario corpus is about
8.4K (§2). Both fit comfortably in context. Even all ten Phase D categories
remain under 16K tokens. The design therefore addresses ordering and
traceability, not context capacity:

| Benefits | Not a goal |
|---|---|
| **Attention:** put likely relevant mitigations near the start | **Capacity:** nothing must be removed to fit |
| **Provenance:** record what was consulted and in what order | **Filtering:** dropping entries would lose information without solving a size problem |
| **Novelty signal:** flag a surface unlike catalog scenarios | |

The mechanism is rank-and-record, not retrieve-and-filter. Phase D still sees
every item in its baseline, ordered by similarity to the threat. No `min_score`
applies to that path (§6). The evaluation in §9 therefore tests whether ordering
changes decisions rather than tuning a filter threshold. The only absolute
threshold is `novel_floor`, which supports the separate claim that a surface is
unlike every catalog scenario.

## 1. Problem

Phases C and D read `src/smith/data/owasp_10_ai_catalog.json` directly:

- **Catalog-order loading.** Phase C takes the full discovery slice, while Phase D takes every mitigation from each applicable category in catalog order. A relevant mitigation may appear hundreds of items into the list. The issue is order, not volume (§0.1).
- **No provenance.** `checkpoint()` receives `catalog` but omits it from `payload["inputs"]` (`security_analysis_checkpoint.py:942-965`), unlike `tool_definitions` / `system_vars` / `guidance`, which all get `{path, sha256}`.
- **Silent staleness.** The only catalog-derived check is a per-ASI scenario count (`:569`). Rewording a scenario leaves the count unchanged, so the checkpoint can pass even though an earlier disposition refers to different content. `guidance_merge.py:201-213` re-verifies guidance hashes but not the catalog hash.

**Goal:** add canonical entry IDs, phase-specific projections, catalog hashes,
and relevance ordering without changing the content each phase is required to
see.

## 2. Catalog facts (measured)

| | Count / size |
|---|---|
| Entries / scenarios | 10 threats, **61** scenarios |
| Retrievable items | **two separate indexes** (§6): 61 scenarios, and 78 `mitigations` + 222 `mitigation_steps` = 300 mitigation items |
| Mean item size | scenario 255 chars; mitigation item 126 chars |
| Phase C discovery slice | ~8.4K tokens (`description`, `attack_scenarios`, `threat_aliases`) |
| Phase D mitigation slice | ~15.6K tokens; ~11.2K for hr-agent's 7 applicable categories |

These figures describe catalog size, not retrieval quality. They do not show
that the current ordering produces worse dispositions. The T1 example below is
also an observation, not a measured result. §9.0 defines the comparison needed
to determine whether ranking improves Phase D, and §10 step 3 checks the example
directly.

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

## 4. Component A — entry store

Add `src/smith/tools/security_catalog.py` as the single catalog parser.

- `load_catalog(path) -> Catalog` with `sha256`, `framework`, `version`, ordered `entries`, `scenario_counts`. **`sha256` is of the bytes this call parsed**, so callers compare the content they actually used (§5) rather than re-reading the path later.
- **Canonical IDs:** `ASI03` (threat), `ASI03#4` (scenario, 1-based — maps onto the existing `Scenario` column, no artifact change), `ASI03/mit#2`, `ASI03/step#5`.

  These IDs are positional rather than permanently stable. Reordering scenarios
  within `ASI03` changes what each `ASI03#n` refers to. The artifact's existing
  `Scenario` column already uses this index, and §7 does not change its schema.
  The new `consulted.C.scenario_ids` state records both the ID and a text hash:
  `{"id": "ASI03#4", "item_sha256": "…"}`. This makes reordering detectable at
  the entry level. A scenario ID should always be interpreted with the catalog
  hash recorded for that run.
- `discovery_projection(catalog)` → `id`, `name`, `description`, `threat_aliases`, `scenarios`. **Mitigation and impact fields are structurally absent**, enforcing `threat_model.md:13-15` mechanically rather than in prose.
- `mitigation_projection(catalog, ids)` → `impact`, `business_impact`, `mitigations`, `mitigation_steps`, `source_url` for exactly those IDs; raises on an unknown ID.
- `_catalog_scenario_counts` (`:569`) becomes a thin delegate with one parse path and one error contract. It preserves the existing `"OWASP catalog is missing/malformed"` messages and adds checks for duplicate or malformed IDs and entries with zero scenarios. A zero-scenario entry currently drops that ASI from `expected` and reduces mandatory coverage.

## 5. Component B — provenance & freshness

Record provenance in `analysis_state.json`, not in phase artifacts. Changing the
artifact schema would invalidate all five committed example sets. State readers
already use `.get()` (`guidance_merge.py:185-213`, `checkpoint.py:453`), so the
new fields require no migration.

Two additive changes in `checkpoint()` (`:942`):

```json
"inputs": { "owasp_catalog": {"path": "…", "sha256": "e3b0c442…"} },
"catalog": {
  "framework": "OWASP Top 10 for Agentic AI Security", "version": "0.1",
  "sha256": "e3b0c442…", "scenario_counts": {"ASI01": 5, "…": "…"}, "scenario_total": 61,
  "index": {"model_id": "all-MiniLM-L6-v2",
            "params": {"top_k": 8, "max_items": 120, "novel_floor": 0.25}},
  "consulted": {
    "C": {"basis": "mandatory-full-coverage+vector-ranking",
          "scenario_ids": [{"id": "ASI01#1", "item_sha256": "…"}, "…"],
          "novel_candidates": [{"surface": "#12", "best_score": 0.19}]},
    "D": {"basis": "applicable-baseline+ranking+cross-category-augment",
          "baseline_ids": ["ASI01/mit#1", "…"],
          "ranked": {"T1": ["ASI01/mit#3", "ASI01/step#7", "…"]},
          "augmented": [{"id": "ASI03/mit#2", "score": 0.58, "threat": "T1"}]}
  }
}
```

The tool derives Phase D's applicable set from Phase C's `Category Assessment`
(`Applicability ∈ {Yes, Partial}`). The model does not supply this set
separately, so it cannot diverge from the checkpointed assessment. For hr-agent,
the set is `ASI01 ASI02 ASI03 ASI05 ASI06 ASI07 ASI09` (7 of 10).

This change enforces an existing rule rather than reducing tokens.
`enforcement_mapping.md:11` already tells Phase D to load mitigations only for
categories marked applicable in Phase C, so a compliant hr-agent run already
reads roughly these seven categories. The ~4.4K-token (28%) difference applies
only to a run that incorrectly loads all ten. The new tool computes the set
from the checkpointed assessment, supplies those IDs, and records the result.

**Freshness gate.** Let `H_rec` be the hash recorded by Phase C and `H_read` the hash of the bytes the current phase actually read:

| Phase | Condition | Outcome |
|---|---|---|
| A, B | catalog not consulted | no check |
| C | mismatch or absent | record `H_read`, pass — re-running C *is* the remediation |
| D | `H_rec` absent | fail: re-run Phase C to record provenance |
| D | `H_read != H_rec` | **fail**: catalog changed after Phase C; re-run C |
| C, D | `--accept-catalog-change` given | record both hashes, pass (see *Intentional upgrades*) |

**Hash the bytes that were read, not the file at checkpoint time.** The phase
reads the catalog before `checkpoint()` records provenance (`:942`). If the
file changes during the phase, a hash taken at checkpoint time could describe
new content while the dispositions describe old content. `load_catalog`
therefore returns the hash of the exact bytes it parsed (§4), and that value is
passed to `checkpoint()` for the `H_read` versus `H_rec` comparison.

`checkpoint()` also re-validates every phase up to the current one (`:884-929`).
Phase D therefore re-runs `_validate_threat_model`. All validations within one
checkpoint call must share one `Catalog` object rather than reading the file
twice.

**Intentional upgrades.** Updating the OWASP catalog is routine maintenance.
Without an override, the freshness gate would require an immediate Phase C
rerun for all five committed examples, even for an editorial-only update.

So `--accept-catalog-change` records the supersession instead of blocking it:

```json
"catalog": {
  "sha256": "<new>",
  "superseded": [{"sha256": "<old>", "accepted_at": "…", "phase": "D"}]
}
```

The artifact keeps its original provenance, while the state records that the
dispositions were based on `<old>`. The flag is not the default; using it is an
explicit assertion that the change is editorial. Changes to scenario counts
still fail the §3 coverage contract. Document the maintenance sequence—bump,
accept, then rerun Phase C for each example—in `CHANGELOG.md` when the catalog
version changes.

Extend the hash loop at `guidance_merge.py:201-213` with `owasp_catalog` so
guidance derived from an unaccepted catalog revision cannot be merged. An entry
recorded under `superseded` counts as accepted. The checks run before artifacts
are written (`:936-941`), so a stale run does not modify files.

Count-based validation catches added or removed scenarios but misses rewording,
reordering, and mitigation edits. The proposed hashes cover all three cases.

## 6. Component C — ranking & cross-category search

### Where

- **Phase D—per-threat ranking (primary).** The phase currently reasons about 14 threats using one 11.2K-token mitigation block in catalog order. The baseline remains every mitigation item from every applicable category (§3). Ranking presents that baseline separately for each threat, with the closest items first. A second operation adds top-_k_ items from non-applicable categories through `exclude_asi`. This cross-category augmentation is the only path that adds content. The hr-agent T1 threat is classified as `ASI01`, while useful mitigations appear in `ASI03` and `ASI02`. Both categories are already applicable, so T1 tests ordering rather than augmentation. §9.0 measures whether that ordering changes Phase D's output.
- **Phase C—advisory ranking (secondary).** Coverage remains complete, so ranking does not reduce the 8.4K slice. It orders scenarios by similarity to attack surfaces and optionally flags a surface when its best match across all 61 scenarios falls below `novel_floor`. Phase C is also the only path where queries have not yet passed checkpoint validation.
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
- **Only `search` is bounded:** apply per-query `top_k`, deduplicate by canonical ID while keeping the maximum score, then apply global `max_items` with at least one result per query. `top_k` limits candidates before deduplication; `max_items` limits total added context. The per-query floor prevents a few high-scoring threats from consuming the full budget. Results stay grouped by query and carry the originating threat (`"threat": "T1"` in §5). Phase C uses the same rule for each `Attack Surfaces` row.
- **`novel_floor` is the only absolute threshold.** A surface whose best similarity across all 61 scenarios falls below the threshold is flagged as a possible novel threat. The threshold affects only the flag; it never adds or removes catalog content. §9.3 evaluates this signal.
- **Queries built from validated artifact fields**, not model prose. This holds exactly for Phase D and only partly for Phase C:
  - Phase D, per `Threat Instances` row: `{Concrete threat} | actor {Actor} | surface {Surface} | severity {Severity}`. `Threat Instances` is a **Phase C** table, already checkpointed and validated before Phase D runs — so the claim holds without qualification.
  - Phase C, per `Attack Surfaces` row: `{Field} | {Source Layer} | {Provenance} | enters at {Enters where}`. `Attack Surfaces` is a **Phase C** table (`security_analysis_checkpoint.py:185`), so at the moment Phase C needs the ranking, those rows are model-written but **not yet validated** — the checkpoint validates the whole phase at once, at the end (`:591-619`). The §6 guarantee therefore does not hold for Phase C as scoped here.

    Resolving it properly would mean splitting Phase C into two checkpointed steps — surfaces, then retrieval, then dispositions — which the current checkpoint cannot express. Rather than restructure the checkpoint, this design **accepts unvalidated queries in Phase C** and relies on §3's invariant: coverage stays total, so a malformed surface row can only misorder the 61 scenarios or produce a spurious novelty hint; it cannot remove a scenario from the mandatory set. Cutting the N/A screen (above) removes the one case where a bad query could have changed a disposition. That is still a weaker guarantee than Phase D's, and it is part of why Phase C ranking is last in §8.
- **Index freshness** (`validate_index`) distinguishes an absent index from a
  stale index because the two conditions require different behavior: absence
  falls back to catalog order, while stale data fails closed.

  | Condition | Outcome |
  |---|---|
  | Index dir absent, or weights unavailable | **Degrade to baseline**, warn once, record `"index": null` in `consulted`. Phase runs with today's content in catalog order — §3's invariant, and a contributor without weights is not blocked from running a phase. |
  | `catalog_sha256`, `model_id`, item-count, or manifest-schema mismatch | **Fail closed.** The index describes different content than the catalog in hand; ranking from it would be wrong rather than merely absent. Remediation is an explicit rebuild. |

  Never silently rebuilds mid-phase either way — that would download weights and change retrieved content under review. Reuses §5's hash, so "catalog changed" is one notion, not two.

## 7. Integration points

| File | Change |
|---|---|
| `src/smith/tools/security_catalog.py` | **new** — entry store, canonical IDs, projections |
| `src/smith/tools/security_catalog_index.py` | **new** — build, load, `rank`, `search`, `validate_index` |
| `src/smith/tools/security_analysis_checkpoint.py` | delegate `:569`; catalog in `input_paths` `:942`; `catalog` block; thread one read-time `Catalog` through both validations `:884-929`; freshness in `checkpoint()` `:872` |
| `src/smith/tools/guidance_merge.py` | add `owasp_catalog` to the hash loop `:201-213`, honouring `superseded` |
| `src/smith/cli.py` | `security_catalog` + `security_catalog_index` branches `:624`, `allowed_flags` `:1027`, `--query` / `--accept-catalog-change` args `:505` (`--phase` exists at `:508`) |
| `opa_policy/.../steps/threat_model.md` | Inputs `:9` → ranked projection; restate that **all** scenarios still need dispositions |
| `opa_policy/.../steps/enforcement_mapping.md` | Inputs `:11` → per-threat ranked baseline + cross-category additions |
| `.env_template`, `.gitignore`, `CHANGELOG.md` | index dir path; index handling per open question 2; `## [Unreleased]` entry + catalog-upgrade workflow |
| `tests/integration/test_security_catalog{,_index}_unit.py` | **new** |

**Unchanged:** the coverage rule at `:729-742`, the canonical catalog, phase
artifact schemas, and all five example artifact sets.

The committed artifacts remain validation-compatible, but the revised
`threat_model.md` and `enforcement_mapping.md` guides may produce different
content. This proposal does not regenerate the examples or detect that drift.
The review claim should therefore be limited to schema and validation
compatibility. Decide separately whether to regenerate the examples, ideally
alongside the catalog-upgrade work in §5.

CLI surface:

```bash
smith --flag security_catalog [--phase C|D]            # hash, counts, the exact projection
smith --flag security_catalog_index [--build]          # build / show manifest + freshness
smith --flag security_catalog_index --query "…" --phase D   # ranked + scored hits, for tuning
smith --flag security_catalog_index --query "…" --no-prefix # same, prefix off (open question 1)
```

## 8. Phasing

**PR 1—provenance.**

1. Entry store + delegate `_catalog_scenario_counts`. Pure refactor; existing tests pass untouched.
2. Projections + `--flag security_catalog`. Read-only.
3. Provenance block + `inputs.owasp_catalog`, hashed at read time. Additive state.
4. Catalog freshness gate + `--accept-catalog-change` + merge guard. First step that can newly *fail* a passing run; needs step 3's record.

**PR 2—ranking, subject to evaluation.**

5. Index build + manifest + `validate_index`. Nothing consumes it yet.
6. `rank`/`search` + `--query`. Resolve open question 1 (prefix on/off), then run §9.0. If ordering does not change Phase D decisions, stop after this step; the provenance work remains useful without runtime ranking.
7. Phase D per-threat ranking + cross-category augmentation. Baseline is the full applicable set (§3), so retrieval degraded to nothing reproduces today exactly.
8. Phase C scenario ordering + novelty signal. Last: unvalidated queries (§6), and the novelty signal needs §9.3's gate. The N/A screen is **out of scope** (§6) — not deferred to this step.

Steps 1–3 and 5–6 do not change phase behavior. Behavioral risk is limited to
steps 4, 7, and 8. Keeping the work in two PRs allows provenance to proceed even
if §9.0 does not support runtime ranking.

## 9. Evaluation gate

Because Phase D no longer filters by `min_score` (§0.1), its evaluation focuses
on whether ordering changes decisions. Open question 1 determines the embedding
text used in that test, and §9.3 evaluates the separate novelty signal.

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
- whether T1 specifically picks up its `ASI03`/`ASI02` mitigations in B but not
  A — the motivating example, and since both categories are applicable for
  hr-agent this is purely an ordering effect;
- items cited in B that the labels call irrelevant — ordering can mislead as
  well as help, by lending the top of the list unearned authority.

A third arm (**C**) adds cross-category candidates from non-applicable
categories. This isolates the only path that adds content. Run it only if B
outperforms A.

**Decision rule.** If arm B does not outperform arm A beyond the within-arm
spread, do not integrate ranking into the phase workflow. The IDs, projections,
provenance, and freshness work in §4–§5 remains independent.

### 9.1 Ground truth

- **Available free:** ASI-level labels in the examples (`Threat Disposition`, 14 rows for hr-agent; `Rules.OWASP`). Sanity gate — does a threat's own category rank top-1 for its own text?
- **Must be built:** no artifact cites individual mitigation items, so item-level ground truth requires manual labels (about 30–60 minutes per example, stored as a fixture). §9.0 depends on this fixture.
- **Sets `top_k`:** `recall@k` for k ∈ {4, 8, 16} on the cross-category path only. Since `rank` drops nothing, `top_k` now bounds only additive candidates, where being wrong costs context rather than coverage — so a coarse value chosen from the curve's knee is sufficient. No crossover analysis is needed.

### 9.2 A second example, for `novel_floor` only

`top_k` and `max_items` are context budgets and do not require cross-example
validation. `novel_floor` does because it is an absolute cosine threshold whose
behavior depends on the vocabulary used by each example.

If step 8 proceeds, label a second committed example and check whether the
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

Store/index: canonical ID round-trip; `load_catalog` reports the hash of the bytes it parsed, not of a later re-read; `scenario_ids` carry per-item hashes; discovery projection has no mitigation **keys**; `mitigation_projection` returns exactly the requested IDs and raises on unknown; today's error messages preserved; new strict cases; counts 61/300; rebuild byte-identical; vectors unit-norm; `search` respects `top_k`/`max_items`/`exclude_asi` and its ≥1-per-query floor; dedupe keeps max score; corpora cannot cross.

**Key invariant and regression tests:**
- **`rank` is order-only:** for every input set, output is a permutation with the same multiset of IDs. This directly tests the §3 invariant.
- Phase D's baseline equals **all applicable categories**, not the threat's own ASI; with the index absent, Phase D's loaded content is byte-identical to today's in catalog order
- `search` with `max_items` smaller than the query count still returns ≥1 hit per query
- a scenario **reworded without changing any count** fails the Phase D checkpoint; the same edit does *not* block a Phase C re-run; and `--accept-catalog-change` lets it through while recording `superseded`
- **mid-phase edit:** catalog bytes change between read and `checkpoint()` → the recorded hash is the one read, and Phase D subsequently fails
- one `checkpoint()` call re-validating C and D uses a single `Catalog` (both validations see identical bytes, `:884-929`)
- Phase C ranking permutes but never shrinks the 61-scenario set; Phase C still fails when any scenario lacks a disposition, with ranking active
- **index absent → degrades and warns**, records `"index": null`, phase passes; **index stale (hash/model/count mismatch) → fails closed**. The two halves of §6's table, which must not be conflated
- no artifact is rewritten when a freshness check fails
- `guidance_merge` refuses to merge after a catalog change, but allows an accepted `superseded` one

End-to-end on `examples/hr-agent` (full A–D set, 14 threats, 61 scenarios), after `make ci`:

1. Run A–D; Phase C still validates with 61 rows; `consulted.D.baseline_ids` covers all items of the 7 applicable categories of §5.
2. Build index; 61 + 300 items; manifest hash matches `inputs.owasp_catalog.sha256`.
3. Query T1's text; confirm `ASI03`/`ASI02` mitigations rank above its own-category items. This checks ordering. The §9.0 comparison determines whether the order changes Phase D's output.
4. **Negative test:** run with the index dir removed → Phase C and D load exactly today's content in catalog order and produce today's artifacts. §3's invariant end to end. (There is no `min_score` to starve on the content path any more — absence of the index *is* the degraded case.)
5. **Staleness:** in a *copy* of the catalog, edit one `attack_scenarios` string without changing its length; re-run Phase D → fails naming Phase C. Passes silently today — that contrast is the acceptance criterion. Repeat with `--accept-catalog-change` → passes, `superseded` recorded.
6. Re-validate the other four examples: no schema bump required. Note this checks validation only, not that the examples match what the revised step guides would now generate (§7).

## 11. Open questions

1. **Embedding text: category-name prefix on or off?** This must be resolved before §9.0. A bare clause such as *"Apply version control."* may lack context, but `f"{name}: {item}"` gives every item in a category the same strong prefix and may weaken within-category ranking. Compare three formats against the §9.1 labels: `{item}`, `{name}: {item}`, and `{name}: {description[:200]} — {item}`. Fix the format before running the arm comparison.
2. **Is MiniLM the right model for these queries?** Queries are pipe-joined metadata (`{Field} | {Source Layer} | …`), while indexed documents are prose clauses. A symmetric sentence-similarity encoder may compress scores for these short, differently structured texts. Ranking is less sensitive to this than `novel_floor`, which is why §9.3 evaluates the threshold separately. The proposal starts with `all-MiniLM-L6-v2` because Smith already uses it (§6). `manifest.model_id` records the choice so it can change later.
3. **Index committed or derived?** A derived, gitignored index requires model weights wherever ranking runs, although an absent index falls back to catalog order. Committing the reproducible 555 KB `.npz` files avoids that setup cost but adds binary files to review. The current preference is to commit them and document how to reproduce them.
4. **`top_k` by severity?** A `Critical` threat may warrant wider cross-category augmentation than a `Low` one. Defer until flat-`k` is measured — and only relevant if §9.0's arm C ships at all.
5. **`impact` / `business_impact` → Phase D.** `threat_model.md:13-15` lists Phase C's fields as IDs, names, descriptions, aliases, scenarios — impact excluded, consistent with Phase C assigning severity from *system* boundaries (`:35-38`). Flagging as the one non-obvious field assignment.
6. **Should the five examples be regenerated against the revised step guides?** §7 changes `threat_model.md` and `enforcement_mapping.md`. Existing artifacts remain valid but may not match new runs. Regeneration requires five complete Phase A–D runs. Decide this alongside the catalog-upgrade workflow in §5.
