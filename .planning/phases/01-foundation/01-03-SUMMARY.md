---
phase: 01-foundation
plan: 03
subsystem: hgnc
tags: [hgnc, gene-mapping, genenames, dynamic-download, tsv-parser]

# Dependency graph
requires:
  - phase: 01-01
    provides: src/aopwiki_rdf/hgnc/ package placeholder and PipelineConfig with hgnc fields
provides:
  - download_hgnc_data function with assertion guard and cache fallback
  - parse_hgnc_genes function producing genedict1/genedict2 identical to monolith
  - hgnc package exporting both functions
affects: [02-gene-mapping, pipeline-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [retry-with-fallback, assertion-guard-min-count, generic-header-skip]

key-files:
  created:
    - src/aopwiki_rdf/hgnc/download.py
    - src/aopwiki_rdf/hgnc/parser.py
    - tests/unit/test_hgnc_download.py
    - tests/unit/test_hgnc_fallback.py
    - tests/unit/test_hgnc_parser.py
  modified:
    - src/aopwiki_rdf/hgnc/__init__.py

key-decisions:
  - "Header skipped unconditionally (first line) to handle both old Synonyms and new Alias symbols formats"
  - "download_hgnc_data takes individual parameters not PipelineConfig -- pipeline.py wires config fields"

patterns-established:
  - "Retry-with-fallback: download attempts N times, then falls back to cached file with warning log"
  - "Assertion guard: validate minimum expected record count before accepting download data"
  - "No module-level side effects: logging and network only inside function calls"

requirements-completed: [GENE-01, GENE-02]

# Metrics
duration: 2min
completed: 2026-03-04
---

# Phase 1 Plan 3: HGNC Download and Parser Summary

**Dynamic HGNC gene download with min-19000 assertion guard, cache fallback, and TSV parser producing genedict1/genedict2 identical to monolith**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-04T18:25:41Z
- **Completed:** 2026-03-04T18:28:14Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Dynamic HGNC download with retry logic and assertion guard (>= 19000 genes)
- Automatic fallback to cached HGNCgenes.txt with warning log on any failure
- HGNC TSV parser extracted from monolith lines 1811-1832 producing identical genedict1/genedict2
- 20 unit tests covering download success, assertion guard, network failure, fallback, logging, and parser output

## Task Commits

Each task was committed atomically:

1. **Task 1: HGNC download module with fallback and tests** - `b116e68` (feat)
2. **Task 2: Extract HGNC TSV parser from monolith** - `2763c1e` (feat)

_TDD workflow: tests written first (RED), then implementation (GREEN) for both tasks._

## Files Created/Modified
- `src/aopwiki_rdf/hgnc/download.py` - Dynamic download with retry, assertion guard, and cache fallback
- `src/aopwiki_rdf/hgnc/parser.py` - TSV parser producing genedict1 (screening) and genedict2 (precision variants)
- `src/aopwiki_rdf/hgnc/__init__.py` - Package exports for download_hgnc_data and parse_hgnc_genes
- `tests/unit/test_hgnc_download.py` - 6 tests for download success, assertion guard, and network failure
- `tests/unit/test_hgnc_fallback.py` - 3 tests for cache fallback and warning logging
- `tests/unit/test_hgnc_parser.py` - 11 tests for parser output structure and correctness

## Decisions Made
- Header line skipped unconditionally (generic first-line skip) to handle both old "Synonyms" and new "Alias symbols" HGNC header formats without brittle string matching.
- download_hgnc_data accepts individual parameters (url, cache_path, timeout, max_retries, min_genes) rather than a PipelineConfig object, keeping the function decoupled from config internals. pipeline.py will wire config fields.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- HGNC download and parser ready for integration in pipeline.py (Phase 2 gene mapping plan)
- Functions tested with mocked network calls; real genenames.org integration tested via existing production pipeline
- genedict1/genedict2 output structure validated against monolith specification

---
*Phase: 01-foundation*
*Completed: 2026-03-04*
