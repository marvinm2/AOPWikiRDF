---
phase: 09-xml-rdf-coverage-audit-gap-fixes-coverage-ratchet
plan: 04
subsystem: xml-rdf-conversion
tags: [xml-03, coverage-ratchet, qc-guard, ci-two-posture, relative-floor, warn-only]
requires:
  - gap-fix-parser-reads
  - gap-fix-writer-emission
  - element-predicate-map
  - coverage-report-json
provides:
  - coverage-ratchet-baseline
  - per-element-triple-guard
  - warn-only-flag
  - two-posture-ci-policy
affects:
  - scripts/qc_delta_guard.py
  - scripts/coverage-ratchet-baseline.json
  - scripts/coverage-report.json
  - tests/unit/test_qc_delta_guard.py
  - .github/workflows/Turtle_File_Quality_Control.yml
  - .github/workflows/rdfgeneration.yml
tech-stack:
  added: []
  patterns:
    - "Per-element guard reuses the existing gene/total (1 - drop_pct) relative-floor math (D-10) - no absolute magic numbers"
    - "Predicate counted by exact URI via graph.triples((None, URIRef(pred), None)), mirroring count_gene_associations"
    - "element->predicate map is the single source of truth shared by guard + ratchet, read from coverage-ratchet-baseline.json (Open Question #2)"
    - "Two-posture CI by per-workflow flag choice ONLY: strict (no flag) in QC, --warn-only in the weekly run - no github.event_name runtime sniffing"
    - "CI guard steps copy the existing HEAD~1 (QC) / HEAD (weekly) baseline-materialization idiom; missing baseline -> ::warning:: + exit 0"
key-files:
  created:
    - scripts/coverage-ratchet-baseline.json
  modified:
    - scripts/qc_delta_guard.py
    - scripts/coverage-report.json
    - tests/unit/test_qc_delta_guard.py
    - .github/workflows/Turtle_File_Quality_Control.yml
    - .github/workflows/rdfgeneration.yml
decisions:
  - "Froze the ratchet baseline on the POST-fix 80.0% coverage level (76/95, 13 gaps) by regenerating coverage-report.json against the 2026-06-17 snapshot through the merged (gap-fixed) src - D-11 satisfied"
  - "Stored full predicate URIs (not CURIEs) in coverage-ratchet-baseline.json's element_predicates so the guard's URIRef(pred) exact-match counting works without prefix expansion"
  - "test_ratchet_fails_on_drop was already implemented (Plan 03) via the gene relative-floor mechanism and passes as-is; no further change needed in test_coverage_ratchet.py for Task 2"
  - "Rule 1 fix: the test_per_element_relative_floor xfail stub had a self-contradictory body (data wrote new_main=100 but comment/assertion claimed a 100->50 drop must breach). Corrected the fixture to a real 50% drop and added the within-threshold (3%) pass companion the acceptance criteria require"
metrics:
  duration: ~30 min
  completed: 2026-06-18
---

# Phase 9 Plan 04: Coverage Ratchet + Per-Element Guard (XML-03) Summary

Locked in the post-fix coverage as a provable ratchet. Froze `scripts/coverage-ratchet-baseline.json` on the **post-Plan-03 80.0%** level (76/95 covered, 13 gaps) with the 7-element->predicate map as the single source of truth; extended `scripts/qc_delta_guard.py` with a per-element triple-count mode (HEAD~1 relative floor, D-10) and a `--warn-only` flag (D-08); turned the two per-element/warn-only xfail stubs green; and wired both guards into CI with the two-posture policy (**hard-fail in QC, warn-not-block in the weekly run**) via per-workflow flag choice only - no `github.event_name` sniffing. End-to-end verification proves the guard fires on a real `nci:C17469` drop (100->40): strict `main()` exits 1, `--warn-only` exits 0 emitting `::warning::`.

## What Was Built

### Task 1 - per-element mode + --warn-only in qc_delta_guard.py (commit `5ac1e3f`)
- `count_predicate(graph, predicate_uri)` - counts triples by exact URI, the same idiom as `count_gene_associations`.
- `compare_per_element(new_path, baseline_path, element_predicates, drop_pct)` - for each element->predicate pair, counts in new vs baseline and applies the **identical** `baseline > 0 and new < (1 - drop_pct) * baseline` relative floor (D-10). Missing baseline/new file or a parse failure is a hard breach (preserves existing behavior).
- `load_element_predicate_map(path)` - reads `element_predicates` from `coverage-ratchet-baseline.json` (shared source of truth, Open Question #2).
- `run(..., per_element=False, element_predicates=None)` - new optional kwargs; when `per_element=True` it folds per-element breaches into the existing `report["breached"]`/`reasons` aggregation and adds a `report["per_element"]` object. The fixed-gap predicates live in the main TTL, so they are counted there.
- `main()` - new `--coverage-baseline <path>` arg (activates per-element mode) and `--warn-only` flag (on breach, prints `::warning::<reason>` lines and returns 0 instead of 1, D-08). Missing-baseline = hard breach unchanged.
- `print_report` extended with a per-element predicate-count block.
- Removed the two xfail markers in `tests/unit/test_qc_delta_guard.py`; the tests now run as real assertions.

### Task 2 - freeze the post-fix ratchet baseline (D-11) (commit `7451a05`)
- Regenerated `scripts/coverage-report.json` against `data/aop-wiki-xml-2026-06-17` through the merged (gap-fixed) `src/` via the editable install: **72.6% -> 80.0%** (69 -> 76 covered, 20 -> 13 gaps). All 7 Plan-03 fixed-gap elements now report `covered: true`, `is_gap: false`. The audit is idempotent (re-run reproduces the committed report byte-for-byte after sort).
- Wrote `scripts/coverage-ratchet-baseline.json` (`json.dump(..., indent=2, sort_keys=True)`): the post-fix `coverage_pct` (80.0), `covered_element_count` (76), the full sorted `covered_elements` set (the ratchet floor), and `element_predicates` - the 7-element->full-predicate-URI map cross-checked against 09-03-SUMMARY. `git check-ignore` exits 1 (the file is committed, not ignored).
- `test_ratchet_fails_on_drop` (the Nyquist negative sample) was already implemented in Plan 03 via the gene relative-floor mechanism and passes; all three ratchet tests are green.

### Task 3 - two-posture CI wiring (commit `b8d5a22`)
- `Turtle_File_Quality_Control.yml` Step 5c: per-element guard modeled on the Step 5b HEAD~1 materialization, invoked WITHOUT `--warn-only` so a per-element coverage regression FAILS the PR/push QC job (D-08 hard-fail). `fetch-depth: 2` retained.
- `rdfgeneration.yml` Step 7c: per-element guard modeled on the Step 7b HEAD publish-gate, invoked WITH `--warn-only` so a drop emits `::warning::` and exits 0, keeping the live weekly release unblocked (D-08 warn-not-block). The existing gene/total publish gate remains the hard backstop.
- Strict-vs-warn is the per-workflow flag choice only; no `github.event_name` runtime sniffing in either YAML or the script. Edits are minimal and additive - no existing job step disturbed.

## Verification Results

- `pytest tests/unit/test_qc_delta_guard.py` -> 10 passed, 1 skipped (the backup-dependent self-comparison; no `production-rdf-backup/` in the worktree).
- `pytest tests/integration/test_coverage_ratchet.py` -> 3 passed (test_fixed_gaps_emit, test_additive, test_ratchet_fails_on_drop).
- `pytest tests/unit/test_qc_delta_guard.py tests/integration/test_coverage_ratchet.py tests/unit/test_coverage_audit.py` -> 18 passed, 1 skipped, 0 xfail remaining.
- Both workflow YAMLs parse with `yaml.safe_load`.
- Acceptance greps: QC has `coverage-ratchet-baseline` (2) and `warn-only` (0); weekly has `warn-only` (>=1) and `coverage-ratchet-baseline` (2); `github.event_name` count is 0 in the script and both YAMLs; `fetch-depth: 2` retained in QC; `grep -c warn_only|warn-only` on non-comment guard lines >= 1; no new hardcoded triple floor (`grep -nE '< [0-9]{3,}'` returns 0).
- End-to-end: with `nci:C17469` dropped 100->40 and the real `coverage-ratchet-baseline.json` map, the guard breaches that element; strict `main()` returns 1, `--warn-only` returns 0 and emits the `::warning::` lines.
- Scope fence: `git diff 4f247af | grep -cE 'enable_bern2|enable_iri_labels'` = 0.
- Idempotence (phase gate): re-running `coverage_audit.py` reproduces the committed `coverage-report.json`; the frozen baseline reflects the post-fix coverage (D-11).

## Deviations from Plan

**1. [Rule 1 - Bug] Fixed the self-contradictory `test_per_element_relative_floor` xfail stub.**
- **Found during:** Task 1 (GREEN).
- **Issue:** The Plan-01 stub wrote `_write_pair(..., baseline_main=100, new_main=100)` (no drop) but its comment and assertion claimed "Baseline 100 -> new 50 ... breaches the floor". With equal counts the per-element guard correctly reports no breach, so the assertion could never hold for a correct implementation.
- **Fix:** Changed the fixture to a genuine 50% drop (`new_main=50`), asserted `baseline_count==100`/`new_count==50`/`breached is True`, and added the within-threshold (3%, 100->97) pass companion the Task-1 acceptance criteria require ("a drop within drop_pct passes" - proving the floor is relative, not absolute). Created the `within/` tmp subdir before reuse of `_write_pair`.
- **Files modified:** `tests/unit/test_qc_delta_guard.py`.
- **Commit:** `5ac1e3f`.

**2. [Process] Coverage report regenerated through the editable install (main-repo src).**
The repo's editable install (`.pth`) points at the MAIN repo `src/`, which already has Plan-03's merged gap fixes, so `coverage_audit.py` correctly produced the post-fix 80.0% report. The XML snapshot (`data/aop-wiki-xml-2026-06-17`) also lives only in the main repo (`data/` is gitignored, absent from the worktree); it was referenced by absolute path. Not a code change. The qc_delta_guard tests load the guard by absolute path from the worktree, so they validate the worktree code regardless of the `.pth`.

## Threat Model Compliance

- **T-09-07 (Tampering, weekly auto-commit of degraded data - mitigate):** `--warn-only` keeps the weekly run unblocked while loudly surfacing per-element drops as `::warning::`; the existing gene/total publish-gate delta-guard remains the hard backstop (unchanged `--drop-pct`). PR/push QC hard-fails on per-element coverage regression. Verified end-to-end (strict exit 1, warn exit 0).
- **T-09-08 (Spoofing/Repudiation, stale baseline - mitigate):** Baseline frozen AFTER the gap-fixes (D-11); missing baseline = hard breach (preserved); the baseline + element->predicate map are committed as sorted JSON under PR review.
- **T-09-SC (supply-chain - mitigate):** No package installed; stdlib + already-pinned rdflib/pyyaml only.

## Self-Check: PASSED

- `scripts/qc_delta_guard.py` - FOUND (per-element mode + --warn-only)
- `scripts/coverage-ratchet-baseline.json` - FOUND (80.0%, 76 covered, 7-element map; not gitignored)
- `scripts/coverage-report.json` - FOUND (regenerated to post-fix 80.0%)
- `tests/unit/test_qc_delta_guard.py` - FOUND (xfails removed, 2 stubs green)
- `.github/workflows/Turtle_File_Quality_Control.yml` - FOUND (Step 5c strict)
- `.github/workflows/rdfgeneration.yml` - FOUND (Step 7c --warn-only)
- Commit `5ac1e3f` (Task 1) - present in git history
- Commit `7451a05` (Task 2) - present in git history
- Commit `b8d5a22` (Task 3) - present in git history
