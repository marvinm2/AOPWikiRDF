---
phase: 07-promote-bern2-to-primary-union-preserved
plan: 02
subsystem: ner-el-mapper
tags: [bern2, ner, ker, cache-integrity, union, degradation, tdd]
requires:
  - "07-01: _partial cache marker (KER NER trusts the cache)"
  - "Phase 6: NerResult failure signalling, map_ner_genes_in_kes_result, report_cache_coverage/is_cached, _description_text normaliser, _write_gene_block :geneDetectedByNER emission"
provides:
  - "_KER_NER_FIELDS + _ker_ner_texts: single source of truth for the 3 KER NER text fields (dc:description + nci:C80263 + edam:data_2042)"
  - "map_ner_genes_in_kers scans all 3 KER fields; report_cache_coverage counts all 3 and requires ALL cached per KER"
  - "map_ner_genes_in_kers_result (NerResult-returning, degradation parity)"
  - "_apply_bern2_enrichment KER branch builds the regex ∪ NER union with regex fallback on outage"
affects:
  - "src/aopwiki_rdf/mapping/ner_el_mapper.py (KER NER + probe)"
  - "src/aopwiki_rdf/pipeline.py (_apply_bern2_enrichment KER branch)"
tech-stack:
  added: []
  patterns:
    - "Single-source-of-truth corpus helper (_ker_ner_texts) shared by mapper + probe + warmer so cache keys always agree"
    - "Per-KER 'cached' = ALL field texts cached (D-09b); probe branches KE (single field) vs KER (three fields) on presence of nci:C80263/edam:data_2042"
    - "KER NerResult failed only when EVERY field lookup failed — composes with 07-01 _partial (a partial multi-field result stays failed=False)"
    - "KER union branch mirrors the KE branch byte-for-byte (regex order preserved, NER-only appended sorted, gene_hgnclist guarded by existing_hgnc)"
key-files:
  created:
    - tests/unit/test_ker_ner_fields.py
    - tests/integration/test_ker_ner.py
  modified:
    - src/aopwiki_rdf/mapping/ner_el_mapper.py
    - src/aopwiki_rdf/pipeline.py
decisions:
  - "report_cache_coverage detects a KER by the presence of any extra NER field (nci:C80263 or edam:data_2042); pure KEs keep single-dc:description counting byte-unchanged"
  - "map_ner_genes_in_kers_result marks a KER failed=True ONLY when EVERY one of its field lookups failed (a true per-KER outage); a mixed multi-field outcome keeps the genes found and stays failed=False (no spurious regex degradation), composing with the 07-01 _partial semantics"
  - "KER degradation uses the same ner_fallback_on_failure gate, _ner_degraded marker, and ok/degraded/total log shape as the KE branch"
  - "map_ner_genes_in_kers signature unchanged ((kerdict, config, sleep_after) -> dict[str,set]), so scripts/warm_bern2_cache.py inherits the 3-field scan with no change"
metrics:
  tasks: 3
  files: 4
  completed: 2026-06-01
requirements: [NER-02, GENE-05]
---

# Phase 7 Plan 02: KER NER Method Parity + Union Wiring (D-08/D-09a/D-09b) Summary

BERN2 KER NER now reaches method parity with regex — it scans the same three KER text fields (`dc:description` + `nci:C80263` biological-plausibility + `edam:data_2042` empirical-support) through one shared `_ker_ner_texts` helper, the cache-coverage probe counts all three (a KER is "cached" only when ALL its texts are cached), and each KER's `edam:data_1025` is wired into the regex ∪ NER union with `:geneDetectedByNER` on the KER subject and regex fallback on a BERN2 outage. All behind `enable_bern2` (default False), so flag-off output is byte-unchanged.

## What Was Built

**D-09a — 3-field KER corpus.** Added `_KER_NER_FIELDS = ("dc:description", "nci:C80263", "edam:data_2042")` and `_ker_ner_texts(props) -> list[str]`, which normalises each present, non-blank field through the existing `_description_text` (the one normaliser — no second one written) and collects the blocks in field order. `map_ner_genes_in_kers` was refactored to annotate every text in `_ker_ner_texts(props)` and union the per-text HGNC sets per KER (previously it scanned only `dc:description`). Its signature is unchanged, so `scripts/warm_bern2_cache.py` inherits the expanded corpus automatically.

**D-09b — probe parity (T-07-04 mitigation).** `report_cache_coverage` now branches per entity: a KER (detected by the presence of `nci:C80263` or `edam:data_2042`) contributes one cache entry per non-empty NER field and is reported uncached unless ALL its field texts are cached; a pure KE keeps the single-`dc:description` counting byte-for-byte. This lands in Task 2 (before the Task 3 run wiring), so the weekly run can never silently hit uncached KER plausibility/empirical text.

**Degradation parity (T-07-05).** `map_ner_genes_in_kers_result` mirrors `map_ner_genes_in_kes_result`, returning a `NerResult` per scanned KER. A KER is `failed=True` only when EVERY one of its field lookups failed (a true per-KER outage); a mixed multi-field outcome keeps the genes found and stays `failed=False` — composing with the 07-01 `_partial` rule, so a single glitchy field never forces a regex-only degradation.

**D-08 — union wiring.** The KER stub in `_apply_bern2_enrichment` (`props["_genes_ner"] = []`) was replaced with the same union logic as the KE branch: call `map_ner_genes_in_kers_result(kerdict, config)`; per KER set `_genes_regex` / `_genes_ner`, build `edam:data_1025` as regex + (NER not already present), extend `gene_hgnclist` with NER-only HGNC IDs guarded by the existing `existing_hgnc` set, and degrade to regex (keeping `edam:data_1025` ≥ regex baseline, marking `_ner_degraded`) on `result.failed`. The writer is unchanged — `_write_gene_block` already emits `:geneDetectedByNER` whenever `_genes_ner` is non-empty.

## Tasks

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 (RED) | 3-field scan + probe-counts-all-three + cached-requires-all + union/degradation tests | 35881f8 | tests/unit/test_ker_ner_fields.py, tests/integration/test_ker_ner.py |
| 2 (GREEN) | `_KER_NER_FIELDS`/`_ker_ner_texts`, 3-field `map_ner_genes_in_kers`, branched probe, `map_ner_genes_in_kers_result` | 334ad20 | src/aopwiki_rdf/mapping/ner_el_mapper.py |
| 3 (GREEN) | KER union branch in `_apply_bern2_enrichment` (D-08) | c6358d0 | src/aopwiki_rdf/pipeline.py |

## TDD Gate Compliance

- RED commit `35881f8` (`test(07-02): RED — ...`) precedes the implementation; both new test files were verified failing against the unmodified source (`_ker_ner_texts` undefined; `map_ner_genes_in_kers_result` absent).
- GREEN commits `334ad20` (`feat(07-02): 3-field KER NER ...`) and `c6358d0` (`feat(07-02): wire KER NER union ...`) make the tests pass.
- No REFACTOR commit needed (implementation was minimal and mirrored existing siblings).

## Verification

- `pytest tests/unit/test_ker_ner_fields.py tests/integration/test_ker_ner.py` → all pass (3-field helper, probe counts all three, cached-requires-all, KER union ⊇ regex, `:geneDetectedByNER` on KER subjects, BERN2 outage degrades to regex).
- `pytest tests/unit/test_ner_cache_coverage.py tests/unit/test_partial_chunk_cache.py tests/unit/test_ner_graceful_degradation.py tests/unit/test_bern2_pipeline.py tests/unit/test_ner_el_mapper.py` → no regression to KE coverage, the 07-01 `_partial` fix, KE degradation, or the existing pipeline/mapper contracts.
- `pytest tests/integration/test_compat_flag_off.py` → passes/skips (COMPAT-01 byte-identity preserved; flag-off KER output unchanged).
- Aggregate focused run: **88 passed, 2 skipped, 0 failed** (the 2 skips are COMPAT-01 byte-diff guards that need `production-rdf-backup/` and an opt-in env flag).
- Acceptance greps: `_ker_ner_texts`/`_KER_NER_FIELDS` defined in `ner_el_mapper.py` and called by both `map_ner_genes_in_kers` and `report_cache_coverage`; `map_ner_genes_in_kers_result` returns `NerResult`; `pipeline.py` KER branch calls `map_ner_genes_in_kers_result` (stub `_genes_ner = []` removed).

All runs used `PYTHONPATH=<worktree>/src` (see Deviations — editable-install gotcha).

## Deviations from Plan

### [Rule 3 - Blocking issue] Editable-install resolves to the main repo, not the worktree

- **Found during:** Task 1 RED verification.
- **Issue:** The `aopwiki_rdf` editable install pins its import path to the MAIN repo's `src/`, not the worktree, so `python -m pytest` from the worktree imported the unmodified main-repo modules and my edits were invisible. This is the documented shared-editable-install gotcha (project MEMORY).
- **Fix:** Run all test commands with `PYTHONPATH=<worktree>/src` so the worktree source shadows the editable install (verified `import aopwiki_rdf.mapping.ner_el_mapper` then resolves to the worktree path). No source change — execution-environment workaround. The orchestrator's merge back to main makes the change live there normally.
- **Files modified:** None (workflow-only).
- **Commit:** n/a.

## Deferred Issues

The full `pytest tests/` run does not complete in a bounded time in this worktree because it includes integration tests that make live network calls (BERN2 hosted API / URI-resolvability / BridgeDb webservice) and hang without connectivity — these are pre-existing, environment-dependent, and unrelated to this plan. The plan-relevant deterministic, mocked suites all pass (88 passed / 2 skipped above). The 4 pre-existing `tests/unit/test_rdf_writer.py::TestDualPredicateChemicalsAndProteinOntology` failures noted in `deferred-items.md` (07-01) remain out of scope (SCOPE BOUNDARY) — untouched by this plan.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary surface. The change is internal to the BERN2 KER NER + cache-probe layer and the pipeline KER branch, flag-gated off in production (`enable_bern2=False`). It mitigates T-07-04 (uncached KER plausibility/empirical text via the all-three-fields probe landing before the run wiring) and T-07-05 (BERN2 KER outage degrading to regex via `map_ner_genes_in_kers_result`).

## Self-Check: PASSED

- `src/aopwiki_rdf/mapping/ner_el_mapper.py` — FOUND (modified; `_KER_NER_FIELDS`, `_ker_ner_texts`, `map_ner_genes_in_kers_result` present).
- `src/aopwiki_rdf/pipeline.py` — FOUND (modified; KER union branch present, stub removed).
- `tests/unit/test_ker_ner_fields.py` — FOUND (created).
- `tests/integration/test_ker_ner.py` — FOUND (created).
- Commit `35881f8` — FOUND (RED).
- Commit `334ad20` — FOUND (GREEN, mapper + probe).
- Commit `c6358d0` — FOUND (GREEN, pipeline wiring).
