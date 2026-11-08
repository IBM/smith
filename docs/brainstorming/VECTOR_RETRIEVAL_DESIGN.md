# Design proposal: threat catalog ranking, provenance, and freshness

> **Status (2026-11-08)**
>
> | Part | Steps (§8) | State | Branch |
> |---|---|---|---|
> | Provenance (PR 1) | 1–4 | implemented | `sc/rag-support` |
> | Ranking index and query tool (PR 2) | 5–6 | implemented | `sc/catalog-vector-index` |
> | Ranking inside Phases C and D | 7–8 | not started; gated on §9.0 | — |
>
> §12 lists what still has to exist before the §9.0 evaluation can run. Line
> numbers in §1–§5 refer to `security_analysis_checkpoint.py` at `aec0d00`,
> before PR 1.
>
> The proposal has two independent parts, split in §8:
>
> 1. **Provenance:** `--prepare` writes the exact catalog slice each phase
>    reads into the analysis directory, and the checkpoint verifies that slice
>    against the current catalog. This work is useful on its own.
> 2. **Ranking:** order each phase's catalog entries by relevance and add
>    cross-category candidates in Phase D. This part proceeds only if the
>    evaluation in §9.0 shows that ordering changes decisions. §2 notes that the
>    committed hr-agent run gives ranking less to work with than earlier drafts
>    assumed.
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
cannot detect catalog changes. This proposal adds a small access layer that
writes each phase's catalog slice to a file, records and verifies that file,
and (in PR 2 and steps 7–8) orders its contents by relevance. Each phase receives the same
required content, and the run records exactly what it received.

The implementation uses two small embedding matrices—61 scenario rows and 300
mitigation rows—and exact matrix multiplication. It does not need a vector
database (§6).

### 0.1 Scope of ranking

The mitigation corpus is about 15.6K tokens, and the scenario corpus is about
8.4K (§2). Both fit comfortably in context. Even all ten Phase D categories
remain under 16K tokens, and the committed hr-agent run loads only about 4.3K. The design therefore addresses ordering and
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

- **The model selects its own slice.** `threat_model.md:9` points Phase C at the raw catalog and asks it, in prose (`:13-15`), to skip mitigation fields. `enforcement_mapping.md:11` asks Phase D, in prose, to load mitigations only for applicable categories. Nothing records or checks what was actually read.
- **Catalog-order loading.** Phase C takes the full discovery slice, while Phase D takes every mitigation from each applicable category in catalog order. The issue is order, not volume (§0.1).
- **No provenance.** `checkpoint()` receives `catalog` but omits it from `payload["inputs"]` (`security_analysis_checkpoint.py:942-965`), unlike `tool_definitions` / `system_vars` / `guidance`, which all get `{path, sha256}`.
- **Silent staleness.** The only catalog-derived check is a per-ASI scenario count (`:569`). Rewording a scenario leaves the count unchanged, so the checkpoint can pass even though an earlier disposition refers to different content. `guidance_merge.py:201-213` re-verifies guidance hashes but not the catalog hash.

Hashing the catalog file at checkpoint time does not fix the first problem.
`checkpoint()` runs after the phase, so its hash describes the file at the end of
the phase, not what the model read during it. The fix is to give the model a
file and then check that file.

**Goal:** give each phase a recorded, verifiable catalog slice, and (in PR 2 and
steps 7–8) relevance ordering, without changing the content each phase is required to
see.

## 2. Catalog facts (measured)

| | Count / size |
|---|---|
| Entries / scenarios | 10 threats, **61** scenarios |
| Retrievable items | **two separate indexes** (§6): 61 scenarios, and 78 `mitigations` + 222 `mitigation_steps` = 300 mitigation items |
| Mean item size | scenario 255 chars; mitigation item 126 chars |
| Phase C discovery slice | ~8.4K tokens (`description`, `attack_scenarios`, `threat_aliases`) |
| Phase D mitigation slice | ~15.6K tokens; ~4.3K (77 items) for hr-agent's 3 applicable categories |
| Catalog history | one commit (`c189f8d`, 2026-09-09) |
| Repeated mitigation text | 72 texts appear in two or more categories, so the 300 mitigation items hold 176 distinct texts; no text repeats within one category |
| Index size, as built | 573 KB: `mitigations.npz` 477 KB, `scenarios.npz` 96 KB, `manifest.json` |

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
  parses them. `Catalog` carries `sha256`, `framework`, `version`, the ordered
  `threats`, and a `scenario_counts` property.
- **Strict structure.** IDs must be exactly `ASI01`–`ASI10`, each once, and every
  entry needs at least one scenario. A zero-scenario entry currently drops that
  ASI from `expected` (`:729-742`) and quietly reduces mandatory coverage. The
  current catalog passes all of these checks. Existing `"OWASP catalog is
  missing/malformed"` messages are kept.
- **Scenario IDs** `ASI03#4` (1-based) match the existing `Scenario Coverage`
  column, so no artifact changes. Mitigation-level IDs (`ASI03/mit#2`,
  `ASI03/step#5`) exist only for ranking and are assigned by the PR 2 index
  (`catalog_items`, §6).
- `build_snapshot(catalog, "C")` returns `id`, `name`, `description`,
  `threat_aliases`, and `attack_scenarios` for all ten entries. Mitigation and
  impact keys are absent from the output.
- `build_snapshot(catalog, "D", applicable)` returns `id`, `name`, `impact`,
  `business_impact`, `mitigations`, `mitigation_steps`, and `source_url` for
  exactly the `applicable` IDs, in catalog order, and raises on an unknown ID.
- `write_snapshot` writes with sorted keys; `snapshot_drift` names the first
  item where a snapshot differs from the current catalog (§5).
- `_validate_threat_model` takes a `Catalog` instead of a `Path`.
  `checkpoint()` loads the catalog once and passes the same object to every
  validation in that call (`:884-929`), so Phase C and Phase D re-validation see
  the same bytes. `_catalog_scenario_counts` (`:569`) is removed; nothing else
  called it, and its error messages now come from `load_catalog`.

## 5. Component B — catalog snapshots and freshness

### The model reads a snapshot, not the catalog

`--prepare` already resets a phase and writes its JSON template
(`prepare_phase`, `:476`). It now also writes the catalog slice the phase
should read:

| Prepare | Writes | Contents |
|---|---|---|
| `--phase C` | `owasp_catalog_C.json` | `build_snapshot(catalog, "C")` + catalog `framework`, `version`, `sha256` |
| `--phase D` | `owasp_catalog_D.json` | `build_snapshot(catalog, "D", …)` for the categories Phase C marked `Yes` or `Partial` + the same header |

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

### Freshness gate

At checkpoint, for the current phase and every earlier catalog phase, rebuild
the projection from the current catalog and compare it with the snapshot on
disk:

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

## 6. Component C — ranking & cross-category search

### Where

- **Phase D—per-threat ranking (primary).** For the committed hr-agent run, the phase reasons about 14 threats using one ~4.3K-token, 77-item mitigation block (`ASI01`, `ASI02`, `ASI06`) in catalog order. The baseline remains every mitigation item from every applicable category (§3). Ranking presents that baseline separately for each threat, with the closest items first. A second operation adds top-_k_ items from non-applicable categories through `exclude_asi`. This cross-category augmentation is the only path that adds content.

  **The motivating example needs restating.** Earlier drafts described an
  `ASI01` threat "T1" whose useful mitigations sit in `ASI03` and `ASI02`, and
  called it an ordering test because both categories were applicable. In the
  committed artifact, IDs are `T01`–`T14`, the only `ASI01` threat is `T12`
  (direct plan injection), and `ASI03` is marked `No`. If `ASI03` mitigations
  help `T12`, that is an **augmentation** case (arm C in §9.0), not ordering.
  With 77 items, the ordering-only case on hr-agent is weak. §9.0 should use an
  example with more applicable categories, or accept that arm B may show no
  effect here.
- **Phase C—advisory ranking (secondary).** Coverage remains complete, so ranking does not reduce the 8.4K slice. It orders scenarios by similarity to attack surfaces and optionally flags a surface when its best match across all 61 scenarios falls below `novel_floor`. Phase C is also the only path where queries have not yet passed checkpoint validation.
- **Out of scope—the N/A pre-screen.** Earlier drafts used retrieval to label likely-`N/A` scenarios before analysis. That hint could anchor the model and change a disposition, while testing the effect would require a larger Phase C experiment (§9.3). This proposal leaves the pre-screen out. It can be reconsidered with a dedicated evaluation.
- **Rejected:** retrieving category *descriptions*. All 10 are required for `Category Assessment` regardless.

### How (steps 5–6, implemented)

**No new dependencies.** `numpy`, `scikit-learn`, and
`sentence-transformers` are already listed in `[project.dependencies]`
(`pyproject.toml:33-46`). The project already uses the 384-dimensional
`all-MiniLM-L6-v2` encoder (`red_feedback.py:106`, `classify_guidance.py:21`,
`tier2_semantic.py:24`).

**Storage: NumPy matrices rather than a vector database.** The two indexes total
361 rows × 384 float32 values. Exact cosine similarity requires one matrix
multiplication per index. FAISS or Chroma would add a dependency without a
practical benefit at this size.

`src/smith/tools/security_catalog_index.py`:

```python
def build_index(catalog_path, index_dir, *, model_id="all-MiniLM-L6-v2",
                prefix=True) -> str: ...
def validate_index(index_dir, catalog) -> dict | None:
    """Manifest if fresh, None if absent; raises if stale."""

class CatalogIndex:
    @classmethod
    def load(cls, index_dir, catalog) -> CatalogIndex | None: ...

    def rank(self, queries, *, corpus: Literal["scenarios", "mitigations"],
             restrict_asi=()) -> list[list[Hit]]:
        """Order the corpus (or the restrict_asi part) per query. Drops nothing."""

    def search(self, queries, *, corpus, top_k=None, max_items=None,
               exclude_asi=()) -> list[Hit]:
        """Bounded additional candidates from outside exclude_asi."""
```

A `Hit` carries `id`, `asi`, `score`, the index of the `query` it answers, and
the item `text`.

The two entry points serve different purposes (§0.1). `rank` reorders an
existing set and has no threshold, so it cannot remove a baseline item.
`search` returns bounded additions from outside the baseline.

- **Artifact:** `references/security_catalog_index/{manifest.json, scenarios.npz, mitigations.npz}`, or `SECURITY_CATALOG_INDEX_DIR` (`.env_template`). Gitignored for now; open question 3.
- **Manifest:** `schema` (`owasp-catalog-index-v1`), `catalog_sha256`, `model_id`, `prefix`, `dimensions`, `counts`, and `params` (`top_k` 8, `max_items` 120). `catalog_sha256` is the PR 1 catalog hash, so "the catalog changed" means the same thing in both places.
- **Canonical IDs** (`catalog_items`): `ASI03#4` for scenarios, matching `Scenario Coverage`; `ASI03/mit#2` and `ASI03/step#5` for mitigations, with each entry's mitigations before its steps. Like scenario IDs they are positional, so read them with the catalog hash.
- **Two separate indexes** so a scenario query can never return a mitigation item — Phase C field discipline enforced structurally. An unknown corpus raises.
- Vectors L2-normalized, so the one absolute threshold (`novel_floor`, step 8) is comparable across runs. `rank` breaks ties in catalog order, and rebuilds are byte-identical.
- **Embedding text** (`embedding_text`): `f"{entry.name}: {item_text}"` by default, raw item text with `--no-prefix`. Short clauses such as *"Apply version control."* lack context, but the same category name on roughly 30 items may reduce within-category separation and make cross-category comparison depend too heavily on category labels. The third candidate format, `{name}: {description[:200]} — {item}`, is not built yet (open question 1, §12).
- **Only `search` is bounded:** apply per-query `top_k`, deduplicate by canonical ID keeping the maximum score, then cap the total at `max_items`. Every query that has a candidate keeps its best one **even past `max_items`**, so a few high-scoring threats cannot consume the full budget. Results stay grouped by query.
- **`search` skips text the baseline already holds.** The catalog repeats 72 mitigation texts across categories (§2): `ASI01/step#1` and `ASI09/step#1` are the same sentence. Without this rule, cross-category search would "add" content Phase D already reads from an applicable category, and arm C in §9.0 would measure duplicates. An item outside `exclude_asi` is eligible only if its text does not appear inside it.
- **`novel_floor` is the only absolute threshold.** A surface whose best similarity across all 61 scenarios falls below the threshold is flagged as a possible novel threat. The threshold affects only the flag; it never adds or removes catalog content. Not built; step 8, gated by §9.3.
- **Queries built from validated artifact fields**, not model prose. This holds exactly for Phase D and only partly for Phase C. **Not built:** `--query` takes free text, so building queries from these rows is the first item in §12.
  - Phase D, per `Threat Instances` row: `{Concrete threat} | actor {Actor} | surface {Surface} | severity {Severity}`. `Threat Instances` is a **Phase C** table, already checkpointed and validated before Phase D runs — so the claim holds without qualification.
  - Phase C, per `Attack Surfaces` row: `{Field} | {Source Layer} | {Provenance} | enters at {Enters where}`. `Attack Surfaces` is a **Phase C** table (`security_analysis_checkpoint.py:185`), so at the moment Phase C needs the ranking, those rows are model-written but **not yet validated** — the checkpoint validates the whole phase at once, at the end (`:591-619`). The §6 guarantee therefore does not hold for Phase C as scoped here.

    Resolving it properly would mean splitting Phase C into two checkpointed steps — surfaces, then retrieval, then dispositions — which the current checkpoint cannot express. Rather than restructure the checkpoint, this design **accepts unvalidated queries in Phase C** and relies on §3's invariant: coverage stays total, so a malformed surface row can only misorder the 61 scenarios or produce a spurious novelty hint; it cannot remove a scenario from the mandatory set. Cutting the N/A screen (above) removes the one case where a bad query could have changed a disposition. That is still a weaker guarantee than Phase D's, and it is part of why Phase C ranking is last in §8.
- **Index freshness** (`validate_index`) distinguishes an absent index from a
  stale index because the two conditions require different behavior: absence
  falls back to catalog order, while stale data fails closed.

  | Condition | Outcome |
  |---|---|
  | Index dir absent | `validate_index` and `CatalogIndex.load` return `None`; status prints `ABSENT`. Once steps 7–8 exist, the phase runs with today's content in catalog order and records `"index": null` — §3's invariant, and a contributor without weights is not blocked. |
  | Manifest schema, `catalog_sha256`, item count, item IDs, or vector shape mismatch | **Fail closed** with a rebuild instruction; status prints `STALE`. The index describes different content than the catalog in hand; ranking from it would be wrong rather than merely absent. |

  Never rebuilds silently; that would download weights and change retrieved
  content under review. Weights that cannot be loaded raise from
  `SentenceTransformer`; step 7 must catch that and degrade like an absent
  index.

**CLI** (`smith --flag security_catalog_index`):

```bash
smith --flag security_catalog_index --build [--no-prefix]   # embed both corpora
smith --flag security_catalog_index                         # FRESH / ABSENT / STALE + manifest
smith --flag security_catalog_index --query "…" --phase C   # rank all 61 scenarios
smith --flag security_catalog_index --query "…" --phase D --asi ASI01,ASI02,ASI06
#   ranks the listed categories' mitigations, then searches the rest
```

**Measured on the shipped catalog** with the real MiniLM: `--build` embeds 61 +
300 items in under a second, and the result is 573 KB and byte-identical across
rebuilds. Querying hr-agent's `T12` text against its applicable set (`ASI01`,
`ASI02`, `ASI06`) reorders all 77 items, led by `ASI01/mit#1` (0.521) and
`ASI02/mit#5` (0.520). `search` then adds 8 candidates from the other seven
categories, led by `ASI03/step#41` (0.372). This shows the mechanism works; it
says nothing about whether Phase D decides better (§9.0).

### Steps 7–8 (not built)

- **Ranked output is the snapshot.** Ranking changes only the order inside the
  §5 snapshot files, so the PR 1 freshness gate and provenance records still
  apply unchanged. The snapshot gains the IDs and scores needed to explain the
  order, using the mitigation-level IDs the index already assigns, and the
  state gains a `consulted` block:

  ```json
  "catalog": {
    "index": {"model_id": "all-MiniLM-L6-v2",
              "params": {"top_k": 8, "max_items": 120, "novel_floor": 0.25}},
    "consulted": {
      "C": {"novel_candidates": [{"surface": "#12", "best_score": 0.19}]},
      "D": {"ranked": {"T12": ["ASI01/mit#3", "ASI02/step#7", "…"]},
            "augmented": [{"id": "ASI03/mit#2", "score": 0.58, "threat": "T12"}]}
    }
  }
  ```

  The baseline set (§3) is already recorded by the snapshot itself, so
  `consulted` records only what ranking adds: order, scores, and augmentation.

## 7. Integration points

**PR 1 — provenance**

| File | Change |
|---|---|
| `src/smith/tools/security_catalog.py` | **new** — `CATALOG_PATH`, `load_catalog`, strict structure checks, `build_snapshot`, `write_snapshot`, `snapshot_drift` |
| `src/smith/tools/security_analysis_checkpoint.py` | `_catalog_scenario_counts` `:569` removed; `_validate_threat_model` `:582` takes a `Catalog`; `checkpoint()` `:872` loads once and runs the freshness gate (`_snapshot_errors`) before writes `:936`; snapshots join `input_paths` `:942` and `owasp_catalog` is recorded from the loaded bytes; `prepare_phase` `:476` gains an optional `catalog` and writes the C/D snapshot; `_reset_phase_outputs` `:461` deletes it |
| `src/smith/tools/guidance_merge.py` | add `owasp_catalog` to the hash loop in `_verify_checkpoint` `:202`; `merge_guidance` takes `catalog`, defaulting to `CATALOG_PATH` |
| `pyproject.toml` | `"data/*.json"` in package data. Built wheels did not include the catalog, so a non-editable install failed Phase C with "OWASP catalog is missing" |
| `opa_policy/.../steps/threat_model.md` | Inputs `:9` → `owasp_catalog_C.json`; drop the prose field rule `:13-15`, now enforced by the file |
| `opa_policy/.../steps/enforcement_mapping.md` | Inputs `:11` → `owasp_catalog_D.json` |
| `opa_policy/.../guidelines-security-analysis.md` | `--prepare` for C and D also writes the snapshot |
| `.gitignore`, `CHANGELOG.md` | `owasp_catalog_*.json` next to line 61; `## [Unreleased]` entry noting in-flight runs must re-run `--prepare` |
| `tests/integration/test_security_catalog_unit.py` | **new** |
| `tests/integration/test_security_analysis_checkpoint_unit.py` | snapshot and freshness cases; existing tests that pass `unused-catalog.json` (`:117`, `:159`) for Phases A/B keep working |

No CLI change: snapshots are written by the existing `--prepare` path.

**PR 2 — ranking index (steps 5–6, as built)**

| File | Change |
|---|---|
| `src/smith/tools/security_catalog_index.py` | **new** — `catalog_items` (canonical IDs), `embedding_text`, `build_index`, `validate_index`, `CatalogIndex.load` / `rank` / `search`, `describe_index`, `query_index` |
| `src/smith/cli.py` | `security_catalog_index` branch and `allowed_flags` entry; `--build`, `--query`, `--asi`, `--no-prefix` args |
| `.env_template`, `.gitignore`, `CHANGELOG.md` | `SECURITY_CATALOG_INDEX_DIR`; `references/security_catalog_index/` ignored (open question 3); `## [Unreleased]` entry |
| `docs/brainstorming/VECTOR_RETRIEVAL_DESIGN.md` | this document |
| `tests/integration/test_security_catalog_index_unit.py` | **new** — 23 offline tests with `FakeEmbedder` |
| `tests/integration/test_security_catalog_index_integration.py` | **new** — 4 opt-in tests with the real MiniLM; skip when the weights are unavailable |

**Steps 7–8 (not built)**

| File | Change |
|---|---|
| `src/smith/tools/security_catalog.py` | ranked snapshot writer |
| `src/smith/tools/security_analysis_checkpoint.py` | `consulted` block; degrade when the index or weights are unavailable |
| `opa_policy/.../steps/*.md` | describe ranked order; restate that **all** scenarios still need dispositions |

**Unchanged in both PRs:** the coverage rule at `:729-742`, the canonical
catalog, and phase artifact schemas.

The committed artifacts remain validation-compatible. The PR 1 guide change
alters only where the model reads the same content from, so it should not
change results. PR 2's ranked order may. Decide separately whether to
regenerate the examples (open question 6).

The PR 2 CLI is listed in §6. Earlier drafts also proposed
`smith --flag security_catalog [--phase C|D]` to print a phase's projection. It
is dropped: `--prepare` already writes that projection as the snapshot file.

## 8. Phasing

**PR 1—provenance.**

1. **Loader.** `security_catalog.py` with `load_catalog` and strict structure
   checks; `_catalog_scenario_counts` delegates and `_validate_threat_model`
   takes a `Catalog`, loaded once per `checkpoint()`. **Not a pure refactor,
   as earlier drafts claimed:** the two tests that call `_validate_threat_model`
   with a path were updated, the stricter checks can reject a catalog the old
   count check accepted, and the packaging fix (§7) landed here.
2. **Snapshots.** Projections, plus `--prepare` writing `owasp_catalog_C.json`
   / `owasp_catalog_D.json`; reset and `.gitignore` handling; snapshots and the
   catalog recorded in `input_paths`; step guides point to the snapshots. Same
   content, new location.
3. **Freshness gate.** Checkpoint compares each snapshot with the current
   projection and fails with the changed item and the phase to re-run. **The
   only step that can newly fail a passing run.**
4. **Merge guard.** `owasp_catalog` added to `_verify_checkpoint`.

Deferred from earlier drafts: mitigation-level IDs (now in PR 2), the
`consulted` block (steps 7–8), `--accept-catalog-change` (§5, open question 7),
and `--flag security_catalog` (dropped, §7).

**Status:** steps 1–4 are implemented on `sc/rag-support`.

**PR 2—ranking, subject to evaluation.**

5. Index build + manifest + `validate_index`. Nothing consumes it yet. **Implemented.**
6. `rank`/`search` + `--query`. **Implemented**, without the evaluation tooling in §12. Resolve open question 1, then run §9.0. If neither ordering nor cross-category additions change Phase D's decisions, stop after this step; the provenance work remains useful without runtime ranking.
7. Phase D per-threat ranking, cross-category augmentation, or both — whichever §9.0 supports — written into the §5 snapshot. Baseline is the full applicable set (§3), so retrieval degraded to nothing reproduces today exactly.
8. Phase C scenario ordering + novelty signal. Last: unvalidated queries (§6), and the novelty signal needs §9.3's gate. The N/A screen is **out of scope** (§6) — not deferred to this step.

Steps 1, 2, 4, 5 and 6 do not change what a passing run produces. Behavioral
risk is limited to steps 3, 7 and 8. Keeping the work in two PRs allows
provenance to proceed even if §9.0 does not support runtime ranking.

## 9. Evaluation gate

Because Phase D no longer filters by `min_score` (§0.1), its evaluation focuses
on whether ordering, or cross-category additions, change decisions. Open question 1 determines the embedding
text used in that test, and §9.3 evaluates the separate novelty signal.

Phases C and D are nondeterministic LLM runs, so one run per arm is not enough.
Run each arm three times at the configured `TEMP`, report per-threat recall and
the range across runs, and count a difference only when it exceeds the
within-arm spread. If the budget allows only one run per arm, report the result
as preliminary rather than conclusive.

### 9.0 Do ordering or cross-category additions change Phase D's output?

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
categories to arm A's content, in catalog order. This isolates the only path that
adds content. **Run it regardless of arm B.** Earlier drafts ran C only if B beat
A, but on hr-agent the ordering case is weak (77 items, §2) while the
motivating example (`T12` and `ASI03`) is an augmentation case, so a null B
would have blocked the more promising test. Use the text-deduplicated `search`
(§6), so arm C adds only content Phase D does not already read.

**Choice of example.** hr-agent's Phase D baseline is 77 items across 3
categories (§2), which gives ordering little room to matter. Run §9.0 on the
committed example with the most applicable categories, or on two examples, so a
null result on a small baseline isn't read as a null result in general.

**Decision rule.** Judge B and C separately against A. Integrate ordering
(step 7) only if B beats A beyond the within-arm spread, and cross-category
additions only if C does; if both help, step 7 ships both. If neither does, do
not integrate ranking into the phase workflow. The loader, snapshots,
provenance, and freshness work in §4–§5 remains independent.

**What running this needs.** Each arm is a Phase D snapshot built from the same
checkpointed Phase C state: A is today's PR 1 snapshot, B reorders it per
threat, C appends the `search` candidates. Producing B and C from an artifact
is not built yet (§12).

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

### PR 1 (implemented)

`test_security_catalog_unit.py` (23 tests) and new cases in
`test_security_analysis_checkpoint_unit.py`; `make ci` passed with 519 unit
tests. The acceptance test was also run against a copy of `car-price-mcp-main`
through the real checkpoint: on `main` it passes, on PR 1 it fails with
`OWASP catalog changed since Phase C was prepared (ASI03#1)`.

Loader and projections: `load_catalog` reports the hash of the bytes it parsed;
today's missing/malformed messages are preserved; new strict cases fail
(duplicate ID, ID outside `ASI01`–`ASI10`, zero-scenario entry); counts are 61
scenarios; the Phase C snapshot has no mitigation or impact **keys**; the
Phase D snapshot holds exactly the requested categories in catalog order and
raises on an unknown one; snapshots are byte-identical across runs.

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

### PR 2, steps 5–6 (implemented)

`test_security_catalog_index_unit.py`, 23 offline tests with `FakeEmbedder`;
`make ci` passed with 542 unit tests.

- Canonical IDs on the shipped catalog: 61 + 300, all distinct; steps follow
  each entry's mitigations.
- Build: unit-norm vectors, manifest contents, no temp files left, prefix on and
  off embed different text, rebuild byte-identical.
- **`rank` is order-only:** each query's output is a permutation of the same
  IDs. This directly tests the §3 invariant. Ties keep catalog order.
- `search`: `top_k` and `exclude_asi` respected; text repeated inside the
  excluded categories is skipped; one hit per query survives `max_items` = 1
  with two queries; duplicates keep the best score; bounds below 1 rejected.
- Corpora cannot cross, and an unknown corpus raises.
- **Index absent → `None` and `ABSENT`; index stale (catalog hash, item count,
  schema) → fails closed.** The two halves of §6's table, which must not be
  conflated.
- CLI: status without an index never constructs an encoder; build then status
  reports `FRESH`; `--query` without `--phase C|D` exits 1; a Phase D query
  prints both sections.

`test_security_catalog_index_integration.py`, 4 opt-in tests with the real
MiniLM: counts and manifest hash, `FRESH` status, an ASI06 scenario's own text
ranks an ASI06 scenario first, and a Phase D query keeps ranked and
cross-category hits in disjoint category sets.

### Steps 7–8 (not built)

- Phase D's ranked snapshot contains exactly the PR 1 snapshot's items; with the index absent it is byte-identical to the PR 1 snapshot.
- Phase C ranking permutes but never shrinks the 61-scenario set; Phase C still fails when any scenario lacks a disposition, with ranking active.
- Index absent or weights unavailable → the phase degrades, warns, records `"index": null`, and passes.

### End to end

On a committed example that re-checkpoints cleanly (see above), after `make ci`:

1. Run `--prepare` + checkpoint for C and D; Phase C validates with 61 rows; `owasp_catalog_D.json` contains exactly the applicable categories; `inputs` records both snapshots and the catalog.
2. **Staleness:** in a *copy* of the catalog, edit one `attack_scenarios` string without changing its length; re-run the Phase D checkpoint → fails naming the scenario and Phase C. Passes silently today; that contrast is the acceptance criterion.
3. (PR 2, done) Build index; 61 + 300 items; manifest hash matches the shipped catalog's sha256.
4. (PR 2, done) Query `T12`'s text on hr-agent; results in §6. This checks the mechanism only; §9.0 decides whether it changes Phase D's output.
5. (Step 7) **Negative test:** with the index dir removed, snapshots are byte-identical to PR 1's. §3's invariant end to end.

## 11. Open questions

1. **Embedding text: category-name prefix on or off?** This must be resolved before §9.0. A bare clause such as *"Apply version control."* may lack context, but `f"{name}: {item}"` gives every item in a category the same strong prefix and may weaken within-category ranking. Compare three formats against the §9.1 labels: `{item}`, `{name}: {item}`, and `{name}: {description[:200]} — {item}`. Fix the format before running the arm comparison. The first two are built (`--no-prefix` and the default); the third is not (§12).
2. **Is MiniLM the right model for these queries?** Queries are pipe-joined metadata (`{Field} | {Source Layer} | …`), while indexed documents are prose clauses. A symmetric sentence-similarity encoder may compress scores for these short, differently structured texts. Ranking is less sensitive to this than `novel_floor`, which is why §9.3 evaluates the threshold separately. The proposal starts with `all-MiniLM-L6-v2` because Smith already uses it (§6). `manifest.model_id` records the choice so it can change later.
3. **Index committed or derived?** A derived, gitignored index requires model weights wherever ranking runs, although an absent index falls back to catalog order. Committing the reproducible `.npz` files (573 KB as built) avoids that setup cost but adds binary files to review. PR 2 gitignores them; anyone running the CLI builds them once with `--build`. Commit them when step 7 makes a phase depend on the index, if setup cost matters more than review cost.
4. **`top_k` by severity?** A `Critical` threat may warrant wider cross-category augmentation than a `Low` one. Defer until flat-`k` is measured — and only relevant if §9.0's arm C ships at all.
5. **`impact` / `business_impact` → Phase D.** `threat_model.md:13-15` lists Phase C's fields as IDs, names, descriptions, aliases, scenarios — impact excluded, consistent with Phase C assigning severity from *system* boundaries (`:35-38`). Flagging as the one non-obvious field assignment.
6. **Should the five examples be regenerated against the revised step guides?** PR 1 changes only where the step guides read catalog content from; PR 2's ranked order may change results. Regeneration requires five complete Phase A–D runs. Decide this after §9.0, together with question 8.
7. **When does `--accept-catalog-change` become worth building?** It is deferred (§5) because no committed example carries `analysis_state.json` and the catalog has changed once. Triggers to revisit: committed state, a regular catalog update cadence, or long-running analyses that a catalog bump would routinely interrupt.
8. **Three examples fail to re-checkpoint on `main`.** `hr-agent`, `employee`, and `RagChatbot_MCPServer` fail Phase C on architecture drift unrelated to the catalog (§10). PR 1 can only assert no regression on the two that pass. Fix the drift first, in a separate PR, so all five can be the regression baseline?
9. **Should repeated mitigation text be collapsed in the catalog itself?** 72 texts appear in two or more categories (§2). `search` works around this (§6), but Phase D's PR 1 snapshot still shows a repeated text once per applicable category it appears in, and §9.1's labels must decide whether a cited repeat counts once or per ID.

## 12. Before the §9.0 evaluation can run

Steps 5–6 make ranking and search exist. They do not yet produce what Phase D
would see under each arm, so §9.0 cannot run from an artifact. Missing, in order:

1. **Queries from `Threat Instances` rows** (§6). `--query` takes free text, so
   arm B and arm C cannot be reproduced from a checkpointed threat model.
2. **Arm snapshots.** A command that reads a checkpointed Phase C state and
   writes the arm B and arm C Phase D snapshots next to the PR 1 snapshot (arm
   A), without changing what `--prepare` writes. Step 7 then only has to make
   the winning arm the default.
3. **The third embedding format** from open question 1.
4. **The §9.1 sanity gate over all threats:** does each threat's own category
   rank first for its own text? The integration test checks one ASI06 scenario.
5. **Item-level labels** (§9.1), about 30–60 minutes per example. Not code; it
   needs an owner.

Items 1–4 are code that can land in this PR or a follow-up. Item 5 blocks the
evaluation itself.
