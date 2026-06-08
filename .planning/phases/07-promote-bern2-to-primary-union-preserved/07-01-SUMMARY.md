---
phase: 07-promote-bern2-to-primary-union-preserved
plan: 01
subsystem: ner-el-mapper
tags: [bern2, cache-integrity, ner, tdd, security]
requires:
  - "Phase 6: NerResult failure signalling, query_bern2 chunking fallback, is_cached/report_cache_coverage"
provides:
  - "_partial cache marker on mixed-chunk BERN2 outcomes (re-warmable miss)"
  - "is_cached + query_bern2 short-circuit treat _partial as a miss"
affects:
  - "src/aopwiki_rdf/mapping/ner_el_mapper.py (BERN2 client cache layer)"
tech-stack:
  added: []
  patterns:
    - "Three-branch merge tail: _error (all-fail) / _partial (mixed) / annotations (all-success)"
    - "Additive _partial keeps NerResult.failed=False (no spurious regex degradation)"
key-files:
  created:
    - tests/unit/test_partial_chunk_cache.py
  modified:
    - src/aopwiki_rdf/mapping/ner_el_mapper.py
decisions:
  - "_partial composes with NerResult as failed=False — a partial result keeps the genes it found and never triggers regex-only degradation; only _error (all-fail) sets failed=True"
  - "Both cache gates (is_cached and query_bern2 short-circuit) gained `and not cached.get('_partial')` so a partial entry is a re-warmable miss"
  - "_errors[:3] stored alongside annotations on _partial for observability, mirroring the _error truncation"
metrics:
  tasks: 2
  files: 2
  completed: 2026-06-01
requirements: [NER-02]
---

# Phase 7 Plan 01: Partial-Chunk Cache Integrity (D-11) Summary

Mixed-outcome chunked BERN2 calls are now cached with a `_partial` marker so the failed chunk is retried instead of silently replayed as complete — closing the silent-gene-loss path (T-06-01/T-06-06 residual) before BERN2 is promoted to primary.

## What Was Built

When `query_bern2` falls back to sentence-bounded chunking and some chunks succeed while others error, the merge tail now has three branches instead of two:

- `not merged and errors` → `{"_error": ...}` (all chunks failed — unchanged).
- `errors` (mixed) → `{"annotations": merged, "_partial": True, "_errors": errors[:3]}` (keep the real genes found, mark the entry as incomplete).
- else → `{"annotations": merged}` (clean all-success — unchanged).

Both cache gates — `is_cached` and the `query_bern2` cache-read short-circuit — gained `and not cached.get("_partial")`, so a `_partial` entry reads as a miss and the failed chunk is re-issued on the next run. `find_hgnc_ids_via_ner_el_result` keys `failed=True` off `"_error"` only, so a `_partial` (which carries `annotations`, no `_error`) stays `failed=False` and contributes its genes additively — it never trips the regex-only degradation path. The change is internal to the BERN2 client; `enable_bern2` stays default False, so production emission is unaffected (no COMPAT-01 exposure).

## Tasks

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 (RED) | Failing test for `_partial` marker, miss, retry, compose | 8ed5ac1 | tests/unit/test_partial_chunk_cache.py |
| 2 (GREEN) | Mark mixed-chunk `_partial`; treat as miss in both gates | 2711d6d | src/aopwiki_rdf/mapping/ner_el_mapper.py, tests/unit/test_partial_chunk_cache.py |

## TDD Gate Compliance

- RED commit `8ed5ac1` (`test(07-01): ...`) precedes the implementation.
- GREEN commit `2711d6d` (`feat(07-01): ...`) makes the test pass.
- No REFACTOR commit needed (implementation was minimal).

The RED test was authored to fail against an unmodified mapper (no `_partial` written); verified failing before the fix. After the fix the 6 new tests pass.

## Verification

- `pytest tests/unit/test_partial_chunk_cache.py` → 6 passed.
- `pytest tests/unit/test_partial_chunk_cache.py tests/unit/test_ner_graceful_degradation.py tests/unit/test_ner_cache_coverage.py` → 38 passed (no Phase 6 degradation/coverage regression).
- `grep -n "_partial" src/aopwiki_rdf/mapping/ner_el_mapper.py` → written in the merge tail (L337) and read in both `is_cached` (L144) and the `query_bern2` short-circuit (L280).

All runs used `PYTHONPATH=<worktree>/src` (see Deviations — editable-install gotcha).

## Deviations from Plan

### [Rule 3 - Blocking issue] Editable-install resolves to the main repo, not the worktree

- **Found during:** Task 2 verification (GREEN run reported the new tests still failing).
- **Issue:** The `aopwiki_rdf` package is installed editable with its import path pinned to the MAIN repo's `src/` (`/home/marvin/.../AOPWikiRDF/src/aopwiki_rdf`), not the worktree. So `python -m pytest` from the worktree imported the unmodified main-repo `ner_el_mapper.py`, and my edits were invisible to the tests. This is the documented shared-editable-install gotcha (project MEMORY: "Shared editable-install gotcha").
- **Fix:** Run all test commands with `PYTHONPATH=<worktree>/src` so the worktree source shadows the editable install. Verified `python -c "import aopwiki_rdf...; print(__file__)"` then resolves to the worktree path. No source change was needed — this is an execution-environment workaround, not a code fix. The orchestrator merges the worktree branch back to the main repo where the editable install will then pick up the change normally.
- **Files modified:** None (workflow-only).
- **Commit:** n/a.

### [Rule 1 - Test correctness] Chunk-aware mock instead of a global call counter

- **Found during:** Task 2 (the RED test's mock used a `requests.post` call counter).
- **Issue:** `_bern2_post` retries up to 3 times per logical call, so a global `requests.post` counter does not align with chunk boundaries — the counter-based mock made every chunk succeed.
- **Fix:** The mock now branches on the POSTed text (`json={"text": ...}`): the full input forces the chunking fallback, the chunk carrying the "first sentence" marker succeeds, every other chunk errors; the BridgeDb call (`data=`, no `json=`) is detected by the absent `json` kwarg.
- **Files modified:** tests/unit/test_partial_chunk_cache.py.
- **Commit:** 2711d6d (test refinement landed with the GREEN commit).

## Deferred Issues

4 pre-existing failures in `tests/unit/test_rdf_writer.py::TestDualPredicateChemicalsAndProteinOntology`
(`skos:exactMatch` assertions on chemical / protein-ontology emission). Verified failing on the clean
base commit `14376e9` with the 07-01 change stashed, so they are independent of this plan and out of
scope (SCOPE BOUNDARY). Logged to `deferred-items.md`.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary surface. The change is internal to the
BERN2 client cache layer and is flag-gated off in production (`enable_bern2=False`). It retires the
T-07-01 / T-06-01 / T-06-06 cache-poisoning-via-partial-result residual.

## Self-Check: PASSED

- `src/aopwiki_rdf/mapping/ner_el_mapper.py` — FOUND (modified, `_partial` present).
- `tests/unit/test_partial_chunk_cache.py` — FOUND (created).
- Commit `8ed5ac1` — FOUND (RED).
- Commit `2711d6d` — FOUND (GREEN).
