# Design Sketch — Threat Catalog Ranking, Provenance & Freshness

> Status: proposal / brainstorming. Nothing implemented.
>
>
> **Shape of the proposal.** Two independent pieces, deliberately split in §8:
> **(1) provenance** — canonical catalog IDs, phase-scoped projections, a
> recorded content hash, a freshness gate. Justified on its own; no measurement
> needed. **(2) ranking** — order each phase's catalog slice by relevance, and
> add cross-category candidates in Phase D. Conditional on §9.0 showing it
> changes a decision; if it does not, piece 1 still ships.
>
> Nothing here filters catalog content by score — see §0.1 for why that would be
> the wrong mechanism for a corpus this size.

## 0. Context for the reader

Smith runs a four-phase security analysis over a target agent before it
generates an OPA policy. Each phase is a markdown step guide the agent follows
(`opa_policy/guidelines-security-analysis/steps/`), and each ends at a
**checkpoint** — `security_analysis_checkpoint.py` validates the phase's
structured output, renders it to a markdown artifact, and appends it to
`analysis_state.json`, the running record every later phase reads.

The phases:

| Phase | Produces |
|---|---|
| A | Architecture inspection — what tools, fields, and subjects exist |
| B | Policy intent — roles, permissions, approval paths, rate limits |
| **C** | **Threat model** — attack surfaces, threat instances, per-scenario coverage |
| **D** | **Enforcement mapping** — who owns each threat; proposed OPA guidance |

Phases C and D are the two that consult **the OWASP catalog**
(`src/smith/data/owasp_10_ai_catalog.json`): a local JSON copy of the *OWASP
Top 10 for Agentic AI Security*, holding 10 threat categories (`ASI01`–`ASI10`),
each with a description, aliases, concrete **attack scenarios**, and
**mitigations**. Phase C decides which catalog scenarios apply to this system;
Phase D decides which mitigations become policy.

Three things about how those two phases read the catalog motivate this
document, and §1 states them precisely: they load whole sections rather than
the relevant entries, they do not record *which* catalog they read, and they
cannot tell that the catalog changed underneath them. The proposal is to put a
small access layer in front of the catalog — canonical IDs per entry, per-phase
projections, a recorded content hash, and relevance ordering — so that each
phase is handed its entries in a useful order and the run records what it was
handed.

The machinery is deliberately modest: two small matrices of sentence embeddings
— 61 scenario rows and 300 mitigation rows — and one matrix multiply, not a
vector database (§6).

### 0.1 What ranking can and cannot buy here

The whole mitigation corpus is ~15.6K tokens and the whole scenario corpus
~8.4K (§2). Both fit in context with room to spare — Phase D could be handed
**all ten categories** and still sit under 16K. **There is no context-capacity
problem to solve**, and that bounds what this design can honestly claim:

| Can buy | Cannot buy |
|---|---|
| **Attention** — ordering, so the relevant mitigation is not item #237 of 300 | **Capacity** — nothing needs to be dropped to fit |
| **Provenance** — a record of what was consulted, in what order | **Relevance filtering** — discarding items is a cost, not a benefit, when they all fit |
| **A novelty signal** — a surface unlike anything in the catalog | |

So the mechanism throughout is **rank-and-record, not retrieve-and-filter**.
Phase D is shown every item it is entitled to see, ordered by similarity to the
threat; nothing is suppressed by a score threshold. This is why no `min_score`
appears on the Phase D path (§6), and why §9 spends its effort on whether
ordering changes decisions rather than on tuning a cutoff. An absolute floor
survives in exactly one place — the novelty signal — because "unlike everything
in the catalog" is inherently a threshold claim.

## 1. Problem

Phases C and D read `src/smith/data/owasp_10_ai_catalog.json` as an ambient file:

- **Unordered bulk loading.** Phase C takes the full discovery slice; Phase D takes every mitigation of every applicable category in catalog order, so a threat's most relevant mitigation may sit 200 items down. Note the problem is *order*, not volume (§0.1).
- **No provenance.** `checkpoint()` receives `catalog` but omits it from `payload["inputs"]` (`security_analysis_checkpoint.py:942-965`), unlike `tool_definitions` / `system_vars` / `guidance`, which all get `{path, sha256}`.
- **Silent staleness.** The only catalog-derived check is a per-ASI *scenario count* (`:569`). A scenario reworded in place keeps the count identical, so the checkpoint passes while the disposition justifying it is now wrong — and every Phase D decision downstream inherits the error. `guidance_merge.py:201-213` re-verifies guidance hashes but not the catalog's.

**Goal:** canonical per-entry IDs, phase-scoped projections, a recorded content hash, and relevance **ordering** over each phase's existing slice — improving what the model attends to first without changing what it is allowed to see.

## 2. Catalog facts (measured)

| | Count / size |
|---|---|
| Entries / scenarios | 10 threats, **61** scenarios |
| Retrievable items | **two separate indexes** (§6): 61 scenarios, and 78 `mitigations` + 222 `mitigation_steps` = 300 mitigation items |
| Mean item size | scenario 255 chars; mitigation item 126 chars |
| Phase C discovery slice | ~8.4K tokens (`description`, `attack_scenarios`, `threat_aliases`) |
| Phase D mitigation slice | ~15.6K tokens; ~11.2K for hr-agent's 7 applicable categories |

These are **catalog and token sizes, not retrieval-quality measurements**. They
say the slices are large enough to be worth ranking; they do not establish that
the current unranked approach produces worse dispositions. 11–15K tokens is not
a large context for current models — see §0.1 for what follows from that — and
the motivating example below (T1) is a judgement, not a measurement; §10 step 3
plans to confirm it, and §9.0 specifies the baseline that would actually settle
it.

## 3. Binding constraint

`security_analysis_checkpoint.py:729-742` builds `expected` as the full ASI×scenario cross-product and errors on any missing row; `:607-611` requires `ASI01`–`ASI10` exactly once. **Phase C must disposition all 61 scenarios and all 10 categories** — the hr-agent artifact carries exactly 61 `Scenario Coverage` rows. Phase D has **no** equivalent rule over mitigations.

> **Invariant.** Retrieval is **additive over a deterministic baseline**, never subtractive. Each phase keeps an ID-exact guaranteed set; retrieval only reorders it and adds to it.
>
> The baseline is pinned to **what the phase reads today**, not to something narrower:
>
> | Phase | Baseline (guaranteed, retrieval-independent) |
> |---|---|
> | C | all 61 scenarios — the coverage contract above |
> | D | all mitigation items of **every applicable category** (`Applicability ∈ {Yes, Partial}`), per `enforcement_mapping.md:11` |
>
> Retrieval contributes **ordering** within that set, plus cross-category items from *non*-applicable categories. With retrieval degraded to nothing, each phase sees exactly today's content in catalog order. That is what makes "never below today" checkable rather than aspirational — and it is why no score threshold gates the Phase D baseline (§0.1).

## 4. Component A — entry store

New `src/smith/tools/security_catalog.py`: the single parse path.

- `load_catalog(path) -> Catalog` with `sha256`, `framework`, `version`, ordered `entries`, `scenario_counts`. **`sha256` is of the bytes this call parsed**, so callers compare the content they actually used (§5) rather than re-reading the path later.
- **Canonical IDs:** `ASI03` (threat), `ASI03#4` (scenario, 1-based — maps onto the existing `Scenario` column, no artifact change), `ASI03/mit#2`, `ASI03/step#5`.

  These are **positional, so they are not stable references**: reorder two
  scenarios within `ASI03` and every recorded `ASI03#n` silently repoints. For
  the artifact's `Scenario` column that is forced — the existing schema is an
  index and §7 does not change artifact schemas. But `consulted.C.scenario_ids`
  in `analysis_state.json` is new, so it carries
  `{"id": "ASI03#4", "item_sha256": "…"}` — a hash of the scenario text — making
  a reorder detectable at the entry level instead of only via the whole-catalog
  hash. Rule of thumb for readers: **a bare `ASI03#4` is only meaningful
  alongside the catalog hash of the run that wrote it.**
- `discovery_projection(catalog)` → `id`, `name`, `description`, `threat_aliases`, `scenarios`. **Mitigation and impact fields are structurally absent**, enforcing `threat_model.md:13-15` mechanically rather than in prose.
- `mitigation_projection(catalog, ids)` → `impact`, `business_impact`, `mitigations`, `mitigation_steps`, `source_url` for exactly those IDs; raises on an unknown ID.
- `_catalog_scenario_counts` (`:569`) becomes a thin delegate — one parse, one error contract. Preserves today's `"OWASP catalog is missing/malformed"` messages, plus new strict checks (duplicate/malformed ID, entry with **zero** scenarios — which currently drops that ASI out of `expected` and silently *reduces* mandatory coverage).

## 5. Component B — provenance & freshness

Recorded in `analysis_state.json`, **not** phase artifacts: a schema bump would invalidate all five committed example artifact sets, and every state reader uses `.get()` (`guidance_merge.py:185-213`, `checkpoint.py:453`), so additions need no migration.

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

Phase D's applicable set is **derived by the tool** from Phase C's `Category Assessment` (`Applicability ∈ {Yes, Partial}`) — never model-supplied, so it cannot drift from what Phase D was entitled to read. For hr-agent: `ASI01 ASI02 ASI03 ASI05 ASI06 ASI07 ASI09` (7 of 10).

The change here is **enforcement, not token count**. `enforcement_mapping.md:11`
already instructs Phase D to load "OWASP mitigations only for categories marked
applicable in Phase C", so a compliant run is already reading roughly these 7
categories; the ~4.4K-token (28%) figure is the gap against loading all ten,
which is the non-compliant case. What is new is that the *tool* computes the
set from the checkpointed `Category Assessment` and hands over exactly those
IDs, so the restriction no longer depends on the model following prose — and
the set it used is recorded.

**Freshness gate.** Let `H_rec` be the hash recorded by Phase C and `H_read` the hash of the bytes the current phase actually read:

| Phase | Condition | Outcome |
|---|---|---|
| A, B | catalog not consulted | no check |
| C | mismatch or absent | record `H_read`, pass — re-running C *is* the remediation |
| D | `H_rec` absent | fail: re-run Phase C to record provenance |
| D | `H_read != H_rec` | **fail**: catalog changed after Phase C; re-run C |
| C, D | `--accept-catalog-change` given | record both hashes, pass (see *Intentional upgrades*) |

**Hash the bytes that were read, not the file at checkpoint time.** The catalog
is read when the phase needs it but `checkpoint()` writes provenance afterwards
(`:942`), so hashing at write time leaves a window: edit the catalog mid-phase
and Phase C records the *new* hash while its dispositions reflect the old
content — after which Phase D sees a match and the staleness §1 calls silent
stays silent. So `load_catalog` returns `sha256` of the exact bytes it parsed
(§4), that value is threaded through to `checkpoint()`, and the comparison is
`H_read` vs. `H_rec`. Re-hashing the path at checkpoint time is the bug this
design exists to close, reintroduced one layer up.

A second-order case the same fix covers: `checkpoint()` re-validates **every**
phase up to the current one (`:884-929`), so Phase D's checkpoint re-runs
`_validate_threat_model` against whatever catalog is live. Both validations in
one `checkpoint()` call must use one `Catalog` object, not two reads.

**Intentional upgrades.** Bumping the OWASP catalog is ordinary maintenance,
and the gate above would make it fail every example's Phase D with "re-run C"
and no way to say "yes, I meant that". Without an escape hatch, a version bump
means a forced Phase C re-run across all five committed example sets — LLM runs,
not a fixture regeneration.

So `--accept-catalog-change` records the supersession instead of blocking it:

```json
"catalog": {
  "sha256": "<new>",
  "superseded": [{"sha256": "<old>", "accepted_at": "…", "phase": "D"}]
}
```

The run proceeds, the artifact keeps its original provenance, and the record
says the dispositions were formed against `<old>`. Deliberately *not* the
default: the flag is the author asserting the change is editorial. A catalog
bump that alters scenario counts still fails the §3 coverage contract on its
own, independent of this flag — the escape hatch covers reword-in-place, not
restructuring. Document the expected workflow (bump → accept → re-run Phase C
per example at leisure) in `CHANGELOG.md` when the catalog version moves.

Also extend the hash loop at `guidance_merge.py:201-213` with `owasp_catalog`, so guidance derived from a superseded catalog cannot be merged — honouring `superseded` so an accepted upgrade does not block a merge. Checks run before artifacts are written (`:936-941`), so a stale run mutates nothing.

**Gap this closes:** count-based validation catches added/removed scenarios but **misses** reword-in-place, reorder, and mitigation edits. All three are silent today.

## 6. Component C — ranking & cross-category search

### Where

- **Phase D — per-threat ranking (primary).** The phase reasons about 14 individual threats against one undifferentiated 11.2K-token block in catalog order. Per §3, the baseline is **every applicable category's mitigation items** — the same content as today, nothing withheld. Retrieval supplies two things on top: (a) a **per-threat ordering** of that baseline, so each threat's prompt leads with its most similar items instead of `ASI01` first; and (b) **cross-category augmentation** — top-_k_ items from *non*-applicable categories via `exclude_asi`, the only genuinely new content, since applicable categories are already fully present. hr-agent's T1 is classed `ASI01` but its real mitigations appear to live in `ASI03`/`ASI02`; both are applicable for hr-agent, so T1's case is answered by **ordering**, not augmentation. §9.0 tests whether that ordering changes Phase D's output at all.
- **Phase C — advisory ranking (secondary).** Coverage stays total, so this cannot shrink the 8.4K slice. Two uses: scenario **ordering** by similarity to attack surfaces, and a **novel-threat signal** where a surface's best similarity across all 61 scenarios falls below `novel_floor`. Phase C's queries are also the one place the validated-input guarantee below does not hold.
- **Out of scope — the N/A pre-screen.** Earlier drafts had retrieval pre-labelling likely-`N/A` scenarios as a hint. Cut: §9.3 shows that testing whether the hint *anchors* the model costs more than the rest of the evaluation combined, and unlike ordering it can change a disposition the model would otherwise have written. Ordering gives Phase C most of the benefit with no such risk. Revisit only with that test run.
- **Rejected:** retrieving category *descriptions*. All 10 are required for `Category Assessment` regardless.

### How

**No new dependencies.** `numpy`, `scikit-learn`, `sentence-transformers` are already in `[project.dependencies]` (`pyproject.toml:33-46`), and `all-MiniLM-L6-v2` (384-dim) is already the project-wide encoder (`red_feedback.py:106`, `classify_guidance.py:21`, `tier2_semantic.py:24`).

**Store: numpy matrices, not a vector DB.** 361 rows across the two indexes × 384 float32 = 555 KB total; exact cosine is one matmul per index. FAISS/Chroma would add a dependency and approximate recall for nothing — ANN pays north of ~10⁵ vectors. `search()` is defined so the backend swaps later.

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

**Two entry points, because the two jobs differ** (§0.1): `rank` reorders a set
the caller already has and **has no threshold** — it cannot suppress a baseline
item, which is what makes §3's invariant mechanical rather than a promise.
`search` is only for the additive cross-category path, where bounding is real
because those items are not in the baseline.

- Artifact: `references/security_catalog_index/{manifest.json, scenarios.npz, mitigations.npz}`, per the `references/` convention. New `SECURITY_CATALOG_INDEX_DIR` in `.env_template` (see open question 2 on committed vs. derived).
- **Two separate indexes** so a scenario query can never return a mitigation item — Phase C field discipline enforced structurally.
- Vectors L2-normalized, so the one surviving absolute threshold (`novel_floor`) is comparable across runs. Deterministic ordering → rebuilds are byte-identical.
- **Embedding text is an open question, not a decision.** The draft embedded `f"{entry.name}: {item_text}"` on the grounds that a bare clause like *"Apply version control."* lacks context. But that stamps one of ten category names onto every item in the category, so the ~30 items of an ASI share a large common component and are compressed against each other — while `search`'s whole job is cross-category discrimination with the own-category signal excluded. The prefix therefore strengthens exactly the axis `exclude_asi` is trying to see past, and it degrades `rank`'s within-category ordering, which is now the primary use. So **the prefix must be measured against no prefix before it is adopted** (open question 1), and that experiment comes before any parameter tuning.
- **Bounding applies to `search` only, in order:** per-query `top_k` → dedupe by canonical ID keeping **max** score → global `max_items` with a **floor of ≥1 per query**. The two knobs are distinct: `top_k` bounds one query's candidates before dedupe; `max_items` is a whole-run context backstop across all queries. A purely global cap would let a few high-scoring threats consume the budget and starve the rest, so the floor guarantees each threat keeps its single best cross-category candidate before any surplus is distributed by score. Hits come back grouped by query, score-descending, carrying the originating threat (the `"threat": "T1"` field in §5) so Phase D's prompt can attribute them. Phase C is one query per `Attack Surfaces` row, same rule per surface.
- **`novel_floor` is the only absolute threshold.** A surface whose best similarity across all 61 scenarios falls below it is flagged as a possible novel threat. It gates a *signal*, never content: nothing is added or removed by it, so a bad value produces a noisy or silent hint and nothing worse. §9.3 is its gate.
- **Queries built from validated artifact fields**, not model prose. This holds exactly for Phase D and only partly for Phase C:
  - Phase D, per `Threat Instances` row: `{Concrete threat} | actor {Actor} | surface {Surface} | severity {Severity}`. `Threat Instances` is a **Phase C** table, already checkpointed and validated before Phase D runs — so the claim holds without qualification.
  - Phase C, per `Attack Surfaces` row: `{Field} | {Source Layer} | {Provenance} | enters at {Enters where}`. `Attack Surfaces` is a **Phase C** table (`security_analysis_checkpoint.py:185`), so at the moment Phase C needs the ranking, those rows are model-written but **not yet validated** — the checkpoint validates the whole phase at once, at the end (`:591-619`). The §6 guarantee therefore does not hold for Phase C as scoped here.

    Resolving it properly would mean splitting Phase C into two checkpointed steps — surfaces, then retrieval, then dispositions — which the current checkpoint cannot express. Rather than restructure the checkpoint, this design **accepts unvalidated queries in Phase C** and relies on §3's invariant: coverage stays total, so a malformed surface row can only misorder the 61 scenarios or produce a spurious novelty hint; it cannot remove a scenario from the mandatory set. Cutting the N/A screen (above) removes the one case where a bad query could have changed a disposition. That is still a weaker guarantee than Phase D's, and it is part of why Phase C ranking is last in §8.
- **Index freshness** (`validate_index`) distinguishes *absent* from *stale*, because §3's invariant and fail-closed pull in opposite directions and conflating them breaks one of the two:

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

**Not touched:** the coverage rule at `:729-742`, the canonical catalog, all phase artifact schemas, all five example artifact sets.

**But "not touched" means validation-compatible, not reproducible.** Two rows
above rewrite `threat_model.md` and `enforcement_mapping.md` — the prompts the
phases run from. The five committed artifact sets will still **validate**
unchanged (no schema moves, so §10 step 6 passes), but they are no longer
byte-identical to what the revised guides would now produce. Nothing in this
design re-generates them, and nothing detects the drift. The claim to make in
review is the narrow one: *schemas and validation are unchanged*. Whether the
examples should be regenerated against the new guides is a separate call, worth
making deliberately rather than discovering later — and it is the same cost
center as §5's catalog-upgrade workflow, so decide both at once.

CLI surface:

```bash
smith --flag security_catalog [--phase C|D]            # hash, counts, the exact projection
smith --flag security_catalog_index [--build]          # build / show manifest + freshness
smith --flag security_catalog_index --query "…" --phase D   # ranked + scored hits, for tuning
smith --flag security_catalog_index --query "…" --no-prefix # same, prefix off (open question 1)
```

## 8. Phasing

**PR 1 — provenance (defensible without any retrieval).**

1. Entry store + delegate `_catalog_scenario_counts`. Pure refactor; existing tests pass untouched.
2. Projections + `--flag security_catalog`. Read-only.
3. Provenance block + `inputs.owasp_catalog`, hashed at read time. Additive state.
4. Catalog freshness gate + `--accept-catalog-change` + merge guard. First step that can newly *fail* a passing run; needs step 3's record.

**PR 2 — ranking (only if PR 1's evidence supports it).**

5. Index build + manifest + `validate_index`. Nothing consumes it yet.
6. `rank`/`search` + `--query`. **Settle open question 1 (prefix on/off) first**, then run §9.0. If §9.0 shows ordering changes no Phase D decision, **stop here** — steps 1–5 stand on their own and §6 is not worth shipping.
7. Phase D per-threat ranking + cross-category augmentation. Baseline is the full applicable set (§3), so retrieval degraded to nothing reproduces today exactly.
8. Phase C scenario ordering + novelty signal. Last: unvalidated queries (§6), and the novelty signal needs §9.3's gate. The N/A screen is **out of scope** (§6) — not deferred to this step.

Steps 1–3 and 5–6 carry no behavior change to any phase; risk is confined to 4, 7, 8. Splitting at the PR boundary matters because PR 1 is the part whose value does not depend on any measurement, and §9.0 can kill PR 2 without wasting it.

## 9. Evaluation gate

Dropping `min_score` from the content path (§0.1) removes most of what earlier
drafts proposed to tune — there is no suppression threshold left to get wrong on
the Phase D path. What remains is one question that decides whether §6 ships at
all (9.0), one design choice feeding it (open question 1), and one gate on the
novelty signal (9.3).

**Phase C and D are LLM runs, so every comparison here is between
nondeterministic samples.** A single pair of runs will differ; that difference
is not evidence. Each arm below is **n = 3 at the configured `TEMP`**, reported
as per-threat recall with its range across runs, and a result counts only if it
exceeds the **within-arm spread**. If three runs per arm is unaffordable, the
honest framing is that §9 yields direction-of-travel rather than a measurement —
say so in the PR instead of reporting n = 1 as though it settled something.

### 9.0 Does per-threat ordering change Phase D's output?

Nothing measured so far shows the current approach falling short (§2), and
retrieval metrics cannot show it: `recall@k` says retrieval *finds* relevant
mitigations, not that Phase D — handed the whole applicable slice, as it is both
before and after this change — would have **missed** them. Only the second claim
justifies §6.

Two arms over the same labelled threats, both seeing identical content, differing
only in order:

| Arm | Phase D sees |
|---|---|
| **A (today)** | all applicable-category items, catalog order |
| **B (ranked)** | all applicable-category items, per-threat similarity order |

Measure, in Phase D's **actual output** rather than in the retrieval result:

- per-threat recall of labelled mitigations, arm B minus arm A;
- whether T1 specifically picks up its `ASI03`/`ASI02` mitigations in B but not
  A — the motivating example, and since both categories are applicable for
  hr-agent this is purely an ordering effect;
- items cited in B that the labels call irrelevant — ordering can mislead as
  well as help, by lending the top of the list unearned authority.

A third arm (**C**) adds cross-category augmentation from non-applicable
categories, isolating the only part of §6 that adds content. Run it only if B
beats A.

**Decision rule.** If arm B does not beat arm A beyond the within-arm spread,
**§6 does not ship**. §4–§5 (IDs, projections, provenance, freshness) stand on
their own and are already a separate PR in §8. This is the single most important
measurement in the document and the cheapest to run, because both arms are
just Phase D.

### 9.1 Ground truth

- **Available free:** ASI-level labels in the examples (`Threat Disposition`, 14 rows for hr-agent; `Rules.OWASP`). Sanity gate — does a threat's own category rank top-1 for its own text?
- **Must be built:** no artifact cites individual mitigation items, so item-level ground truth needs hand-labeling (~30–60 min per example, stored as a fixture). This is the one unavoidable cost; 9.0 cannot run without it.
- **Sets `top_k`:** `recall@k` for k ∈ {4, 8, 16} on the cross-category path only. Since `rank` drops nothing, `top_k` now bounds only additive candidates, where being wrong costs context rather than coverage — so a coarse value chosen from the curve's knee is sufficient. No crossover analysis is needed.

### 9.2 A second example, for `novel_floor` only

`top_k` and `max_items` are context budgets; they do not need cross-example
validation. **`novel_floor` does** — it is the one absolute cosine threshold
left, and its useful value depends on how an example's surface vocabulary
happens to sit against catalog phrasing.

So if step 8 proceeds, label a second example from the other four committed sets
and check that the chosen `novel_floor` still separates surfaces the artifact
marks `novel` from those citing catalog scenarios. If the two examples disagree
beyond a stated tolerance, a single global floor is the wrong shape — make it
per-example-calibrated, or drop the signal. Treat hr-agent as the tuning set and
the second example as the check; do not re-tune on the check.

### 9.3 Gate on the novelty signal

§6 calls the novelty signal the one genuinely new capability, so it needs its
own gate rather than inheriting the ranking result. It is also the most fragile
thing here: with 61 scenarios spanning ten broad categories, most surfaces clear
any low floor, so the signal fires rarely — and when it does, the likeliest
cause is **vocabulary distance, not novelty**. A surface like *"PTO balance
field"* is lexically far from catalog prose while being perfectly well covered
by it.

**Gate:** on labelled examples, do surfaces flagged below `novel_floor`
correspond to threats the artifact's `Threat Instances` marks `novel`
(`catalog basis = novel`)? That label already exists — no new hand-labelling
needed. Report precision and recall of the flag against it.

If flagged surfaces are mostly well-covered ones with unusual wording, **cut the
signal** rather than tuning the floor; a novelty hint that cries wolf is worse
than none, because Phase C has no deterministic fallback to protect the
dispositions it would influence.

**On the N/A pre-screen.** Earlier drafts included it, and testing whether
showing a *probably N/A* hint **anchors** the model requires a three-arm Phase C
comparison (no screen / shown / computed-but-withheld) at n = 3 each — more than
the rest of §9 combined, for a feature that can change a disposition the model
would otherwise have written. §6 cuts it from scope for that reason. Recorded
here so the cost is visible if anyone proposes it again.

## 10. Tests & verification

Unit lane (`-m unit`): env-free, offline, `tmp_path`-confined, per `tests/integration/TESTING_GUIDE.md`. `make unit` forbids weight downloads, so import `SentenceTransformer` at module scope and let tests patch it, following `test_red_suggestion_unit.py:65` / `test_case_evaluation_unit.py:187`. A fake encoder also makes scores deterministic enough to assert thresholds.

Store/index: canonical ID round-trip; `load_catalog` reports the hash of the bytes it parsed, not of a later re-read; `scenario_ids` carry per-item hashes; discovery projection has no mitigation **keys**; `mitigation_projection` returns exactly the requested IDs and raises on unknown; today's error messages preserved; new strict cases; counts 61/300; rebuild byte-identical; vectors unit-norm; `search` respects `top_k`/`max_items`/`exclude_asi` and its ≥1-per-query floor; dedupe keeps max score; corpora cannot cross.

**Invariant and regression tests — the ones that matter:**
- **`rank` is order-only:** for every input set, output is a permutation — same multiset of IDs, nothing dropped. The mechanical form of §3, and the test that would have caught the own-ASI-baseline error in an earlier draft
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
3. Query T1's text; confirm `ASI03`/`ASI02` mitigations rank above its own-category items. This checks *ordering*; §9.0's arm comparison is what shows Phase D's output changes because of it.
4. **Negative test:** run with the index dir removed → Phase C and D load exactly today's content in catalog order and produce today's artifacts. §3's invariant end to end. (There is no `min_score` to starve on the content path any more — absence of the index *is* the degraded case.)
5. **Staleness:** in a *copy* of the catalog, edit one `attack_scenarios` string without changing its length; re-run Phase D → fails naming Phase C. Passes silently today — that contrast is the acceptance criterion. Repeat with `--accept-catalog-change` → passes, `superseded` recorded.
6. Re-validate the other four examples: no schema bump required. Note this checks validation only, not that the examples match what the revised step guides would now generate (§7).

## 11. Open questions

1. **Embedding text: category-name prefix on or off?** — *blocking, settle before §9.0.* `f"{name}: {item}"` was adopted on the reasoning that a bare clause like *"Apply version control."* lacks context. But it stamps one of ten category names onto every item in that category, compressing the ~30 items of an ASI against each other — which hurts `rank`'s within-category ordering (now the primary use) and strengthens precisely the axis `exclude_asi` wants to see past. Three candidates, measured on §9.1's labels via `--no-prefix`: bare `{item}`, `{name}: {item}`, and `{name}: {description[:200]} — {item}` (triples build cost, may dilute the item signal). **This is a design decision, not a tuning knob** — 9.0's arms are only meaningful once it is fixed.
2. **Is MiniLM the right model for these queries?** Queries are pipe-joined metadata (`{Field} | {Source Layer} | …`); documents are prose clauses. That asymmetry is where a symmetric sentence-similarity encoder is weakest, and its cosines on short text compress into a narrow band — part of why §0.1 moves decisions onto ranks rather than absolute scores. Ranking is fairly robust to this; `novel_floor` is not, which is the real argument for §9.3's gate. Staying with `all-MiniLM-L6-v2` because it is already the project-wide encoder (§6) and adding a second model is a bigger change than this design warrants — but the limitation is real and `manifest.model_id` exists so the choice is recorded and swappable.
3. **Index committed or derived?** Derived + gitignored means **everyone running Phase C or D needs the model weights** to get ranking at all — though with §6's split they are no longer *blocked*: an absent index degrades to today's behavior. Committing 555 KB of `.npz` removes the asymmetry at the price of one binary in review, and the binary is reproducible (deterministic ordering, byte-identical rebuilds), so a reviewer can regenerate and diff rather than trust it. Leaning commit; the draft's original lean toward derived predates both the degrade path and that observation. Author's call.
4. **`top_k` by severity?** A `Critical` threat may warrant wider cross-category augmentation than a `Low` one. Defer until flat-`k` is measured — and only relevant if §9.0's arm C ships at all.
5. **`impact` / `business_impact` → Phase D.** `threat_model.md:13-15` lists Phase C's fields as IDs, names, descriptions, aliases, scenarios — impact excluded, consistent with Phase C assigning severity from *system* boundaries (`:35-38`). Flagging as the one non-obvious field assignment.
6. **Should the five examples be regenerated against the revised step guides?** §7 changes `threat_model.md` and `enforcement_mapping.md`, so the committed artifacts remain valid but cease to be reproducible from the guides that produced them. Regenerating is five Phase A–D runs; not regenerating leaves a silent drift. Same cost center as §5's catalog-upgrade workflow — decide both together.
