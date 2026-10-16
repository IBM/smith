# Design Sketch — Threat Catalog Retrieval, Provenance & Freshness

> Status: proposal / brainstorming. Nothing implemented.

## 1. Problem

Phases C and D read `src/smith/data/owasp_10_ai_catalog.json` as an ambient file:

- **Whole sections load into context.** Phase C takes the full discovery slice; Phase D takes every mitigation of every applicable category, unranked.
- **No provenance.** `checkpoint()` receives `catalog` but omits it from `payload["inputs"]` (`security_analysis_checkpoint.py:942-965`), unlike `tool_definitions` / `system_vars` / `guidance`, which all get `{path, sha256}`.
- **Silent staleness.** The only catalog-derived check is a per-ASI *scenario count* (`:569`). A scenario reworded in place keeps the count identical, so the checkpoint passes while the disposition justifying it is now wrong — and every Phase D decision downstream inherits the error. `guidance_merge.py:201-213` re-verifies guidance hashes but not the catalog's.

**Goal:** canonical per-entry IDs, phase-scoped projections, a recorded content hash, and bounded semantic retrieval that improves relevance without weakening coverage.

## 2. Catalog facts (measured)

| | Count / size |
|---|---|
| Entries / scenarios | 10 threats, **61** scenarios |
| Retrievable items | 61 scenarios + 78 `mitigations` + 222 `mitigation_steps` = **361** |
| Mean item size | scenario 255 chars; mitigation item 126 chars |
| Phase C discovery slice | ~8.4K tokens (`description`, `attack_scenarios`, `threat_aliases`) |
| Phase D mitigation slice | ~15.6K tokens; ~11.2K for hr-agent's 7 applicable categories |

## 3. Binding constraint

`security_analysis_checkpoint.py:729-742` builds `expected` as the full ASI×scenario cross-product and errors on any missing row; `:607-611` requires `ASI01`–`ASI10` exactly once. **Phase C must disposition all 61 scenarios and all 10 categories** — the hr-agent artifact carries exactly 61 `Scenario Coverage` rows. Phase D has **no** equivalent rule over mitigations.

> **Invariant.** Retrieval is **additive over a deterministic baseline**, never subtractive. Each phase keeps an ID-exact guaranteed set; retrieval only adds to it. A bad threshold, stale index, or cold model therefore degrades to today's behavior and never below it.

## 4. Component A — entry store

New `src/smith/tools/security_catalog.py`: the single parse path.

- `load_catalog(path) -> Catalog` with `sha256`, `framework`, `version`, ordered `entries`, `scenario_counts`.
- **Canonical IDs:** `ASI03` (threat), `ASI03#4` (scenario, 1-based — maps onto the existing `Scenario` column, no artifact change), `ASI03/mit#2`, `ASI03/step#5`.
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
  "index": {"model_id": "all-MiniLM-L6-v2", "params": {"top_k": 8, "min_score": 0.25}},
  "consulted": {
    "C": {"basis": "mandatory-full-coverage+vector-ranking",
          "scenario_ids": ["ASI01#1", "…"], "na_screened": ["ASI04#1"], "novel_candidates": ["#12"]},
    "D": {"basis": "category-baseline+vector-augment",
          "baseline_ids": ["ASI01/mit#1"], "retrieved": [{"id": "ASI03/mit#2", "score": 0.58, "threat": "T1"}]}
  }
}
```

Phase D's applicable set is **derived by the tool** from Phase C's `Category Assessment` (`Applicability ∈ {Yes, Partial}`) — never model-supplied, so it cannot drift from what Phase D was entitled to read. For hr-agent: `ASI01 ASI02 ASI03 ASI05 ASI06 ASI07 ASI09` (7 of 10, ~4.4K tokens saved, 28%).

**Freshness gate**, before any phase reads the catalog. Let `H_now` / `H_rec` be the live and recorded hashes:

| Phase | Condition | Outcome |
|---|---|---|
| A, B | catalog not consulted | no check |
| C | mismatch or absent | record `H_now`, pass — re-running C *is* the remediation |
| D | `H_rec` absent | fail: re-run Phase C to record provenance |
| D | `H_now != H_rec` | **fail**: catalog changed after Phase C; re-run C |

Also extend the hash loop at `guidance_merge.py:201-213` with `owasp_catalog`, so guidance derived from a superseded catalog cannot be merged. Checks run before artifacts are written (`:936-941`), so a stale run mutates nothing.

**Gap this closes:** count-based validation catches added/removed scenarios but **misses** reword-in-place, reorder, and mitigation edits. All three are silent today.

## 6. Component C — vector retrieval

### Where

- **Phase D — per-threat mitigation retrieval (primary).** 300 mitigation items, no coverage contract, and the phase reasons about 14 individual threats against one undifferentiated 11.2K-token block. Baseline = mitigation items of the threat's **own** ASI (guaranteed). Augmentation = top-_k_ from other categories via `exclude_asi`, so budget is spent only on cross-category candidates category loading misses. hr-agent's T1 is classed `ASI01`, but its real mitigations live in `ASI03` (privilege scoping) and `ASI02` (tool access).
- **Phase C — advisory ranking (secondary).** Coverage stays total, so this cannot shrink the 8.4K slice. It yields: scenario **ordering** by similarity to attack surfaces; an **N/A pre-screen** (hint only, model still writes every disposition); and a **novel-threat signal** where a surface's best similarity across all 61 scenarios falls below the floor — the one genuinely new capability.
- **Rejected:** retrieving category *descriptions*. All 10 are required for `Category Assessment` regardless.

### How

**No new dependencies.** `numpy`, `scikit-learn`, `sentence-transformers` are already in `[project.dependencies]` (`pyproject.toml:33-46`), and `all-MiniLM-L6-v2` (384-dim) is already the project-wide encoder (`red_feedback.py:106`, `classify_guidance.py:21`, `tier2_semantic.py:24`).

**Store: a numpy matrix, not a vector DB.** 361 × 384 float32 = 555 KB; exact cosine is one matmul. FAISS/Chroma would add a dependency and approximate recall for nothing — ANN pays north of ~10⁵ vectors. `search()` is defined so the backend swaps later.

New `src/smith/tools/security_catalog_index.py`:

```python
class CatalogIndex:
    @classmethod
    def load(cls, index_dir: Path) -> CatalogIndex: ...
    def search(self, queries, *, corpus: Literal["scenarios","mitigations"],
               top_k, min_score, max_items, exclude_asi=()) -> list[Hit]: ...
```

- Artifact: `references/security_catalog_index/{manifest.json, scenarios.npz, mitigations.npz}`, per the `references/` convention. New `SECURITY_CATALOG_INDEX_DIR` in `.env_template`; gitignored (derived binary).
- **Two separate indexes** so a scenario query can never return a mitigation item — Phase C field discipline enforced structurally.
- Embeds `f"{entry.name}: {item_text}"`; a bare clause like *"Apply version control."* lacks context. Vectors L2-normalized so a fixed `min_score` is meaningful across runs. Deterministic ordering → rebuilds are byte-identical.
- **Bounding, in order:** per-query `top_k` → drop `score < min_score` → dedupe by canonical ID keeping **max** score → global `max_items` cap. Makes per-phase context cost predictable.
- **Queries built from validated artifact fields**, not model prose:
  - Phase C, per `Attack Surfaces` row: `{Field} | {Source Layer} | {Provenance} | enters at {Enters where}`
  - Phase D, per `Threat Instances` row: `{Concrete threat} | actor {Actor} | surface {Surface} | severity {Severity}`
- **Index freshness** (`validate_index`) fails closed — never silently rebuilds mid-phase, which would download weights and change retrieved content under review. Rejects: missing dir, unknown manifest schema, `catalog_sha256` mismatch, `model_id` mismatch, item-count mismatch. Reuses §5's hash, so "catalog changed" is one notion, not two.

## 7. Integration points

| File | Change |
|---|---|
| `src/smith/tools/security_catalog.py` | **new** — entry store, canonical IDs, projections |
| `src/smith/tools/security_catalog_index.py` | **new** — build, load, `search`, `validate_index` |
| `src/smith/tools/security_analysis_checkpoint.py` | delegate `:569`; catalog in `input_paths` `:942`; `catalog` block; freshness in `checkpoint()` `:872` |
| `src/smith/tools/guidance_merge.py` | add `owasp_catalog` to the hash loop `:201-213` |
| `src/smith/cli.py` | `security_catalog` + `security_catalog_index` branches `:624`, `allowed_flags` `:1027`, `--query` arg `:505` (`--phase` exists at `:508`) |
| `opa_policy/.../steps/threat_model.md` | Inputs `:9` → ranked projection; restate that **all** scenarios still need dispositions |
| `opa_policy/.../steps/enforcement_mapping.md` | Inputs `:11` → baseline + retrieved mitigations per threat |
| `.env_template`, `.gitignore`, `CHANGELOG.md` | index dir path; ignore derived index; `## [Unreleased]` entry |
| `tests/integration/test_security_catalog{,_index}_unit.py` | **new** |

**Not touched:** the coverage rule at `:729-742`, the canonical catalog, all phase artifact schemas, all five example artifact sets. Retrieval changes what gets *loaded*, never what gets *validated*.

CLI surface:

```bash
smith --flag security_catalog [--phase C|D]            # hash, counts, the exact projection
smith --flag security_catalog_index [--build]          # build / show manifest + freshness
smith --flag security_catalog_index --query "…" --phase D   # scored hits, for tuning
```

## 8. Phasing

1. Entry store + delegate `_catalog_scenario_counts`. Pure refactor; existing tests pass untouched.
2. Projections + `--flag security_catalog`. Read-only.
3. Provenance block + `inputs.owasp_catalog`. Additive state.
4. Catalog freshness gate + merge guard. First step that can newly *fail* a passing run; needs step 3's record.
5. Index build + manifest + index freshness. Nothing consumes it yet.
6. Retrieval API + `--query`. **Tune thresholds here on evidence (§9).**
7. Phase D baseline + augmentation. Lowest risk: baseline alone equals today.
8. Phase C ranking + N/A screen + novel signal. Last — hard coverage contract, and depends on step 6's floor.

Steps 1–3 and 5–6 carry no behavior change to any phase; risk is confined to 4, 7, 8.

## 9. Evaluation gate

Guessed thresholds are the main way this fails quietly. `min_score` too high suppresses real mitigations; too low floods the budget.

- **Available free:** ASI-level labels in the examples (`Threat Disposition`, 14 rows for hr-agent; `Rules.OWASP`). Sanity gate — does a threat's own category rank top-1 for its own text?
- **Must be built:** no artifact cites individual mitigation items, so item-level ground truth needs hand-labeling for hr-agent's 14 threats (~30–60 min, stored as a fixture).
- **Metrics:** `recall@k` for k ∈ {4, 8, 16} → sets `top_k`; relevant-vs-irrelevant score distributions → sets `min_score` at the crossover; Phase C rank distribution of threat-cited vs. `N/A` scenarios.
- **Gate:** if the N/A screen can't separate threat-cited from `N/A` scenarios on existing examples, ship step 7 and **drop step 8** — Phase C's whole value is that separation, and unlike Phase D it has no deterministic fallback.

## 10. Tests & verification

Unit lane (`-m unit`): env-free, offline, `tmp_path`-confined, per `tests/integration/TESTING_GUIDE.md`. `make unit` forbids weight downloads, so import `SentenceTransformer` at module scope and let tests patch it, following `test_red_suggestion_unit.py:65` / `test_case_evaluation_unit.py:187`. A fake encoder also makes scores deterministic enough to assert thresholds.

Store/index: canonical ID round-trip; discovery projection has no mitigation **keys**; `mitigation_projection` returns exactly the requested IDs and raises on unknown; today's error messages preserved; new strict cases; counts 61/300; rebuild byte-identical; vectors unit-norm; `search` respects `top_k`/`min_score`/`max_items`/`exclude_asi`; dedupe keeps max score; corpora cannot cross.

**Invariant and regression tests — the ones that matter:**
- a scenario **reworded without changing any count** fails the Phase D checkpoint; the same edit does *not* block a Phase C re-run
- Phase D with empty augmentation yields exactly the category baseline
- Phase C ranking permutes but never shrinks the 61-scenario set
- Phase C still fails when any scenario lacks a disposition, with retrieval active and `min_score` starved
- no artifact is rewritten when a freshness check fails
- `guidance_merge` refuses to merge after a catalog change

End-to-end on `examples/hr-agent` (full A–D set, 14 threats, 61 scenarios), after `make ci`:

1. Run A–D; Phase C still validates with 61 rows; `consulted.D.mitigation_ids` equals the 7 IDs in §5.
2. Build index; 61 + 300 items; manifest hash matches `inputs.owasp_catalog.sha256`.
3. Query T1's text; confirm `ASI03`/`ASI02` mitigations surface above the floor.
4. **Negative test:** `min_score=0.99` → retrieval returns nothing, both phases still pass with today's output. This is §3's invariant end to end.
5. **Staleness:** in a *copy* of the catalog, edit one `attack_scenarios` string without changing its length; re-run Phase D → fails naming Phase C. Passes silently today — that contrast is the acceptance criterion.
6. Re-validate the other four examples: no schema bump required.

## 11. Open questions

1. **Query context for mitigation items.** `"{name}: {item}"` is the cheap version; if recall@8 is weak, `"{name}: {description[:200]} — {item}"` triples build cost and may dilute the item signal. Decide from §9's numbers.
2. **Index committed or derived?** Derived + gitignored means every contributor needs weights to run a phase; committing 555 KB of `.npz` removes that at the price of a binary in review. Leaning derived — a contributor-experience call.
3. **`top_k` by severity?** A `Critical` threat may warrant wider augmentation than a `Low` one. Defer until flat-`k` is measured.
4. **`impact` / `business_impact` → Phase D.** `threat_model.md:13-15` lists Phase C's fields as IDs, names, descriptions, aliases, scenarios — impact excluded, consistent with Phase C assigning severity from *system* boundaries (`:35-38`). Flagging as the one non-obvious field assignment.
