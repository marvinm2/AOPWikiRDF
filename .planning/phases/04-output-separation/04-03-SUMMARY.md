---
phase: 04-output-separation
plan: 03
subsystem: ci
tags: [github-actions, integration-testing, rdflib, turtle-validation, pytest]

# Dependency graph
requires:
  - phase: 04-output-separation
    provides: write_enriched_rdf function and ENRICHED_PREFIXES constant from plan 01
provides:
  - CI workflows validating four TTL files including AOPWikiRDF-Enriched.ttl
  - 7 integration tests for output separation invariants
affects: [05-validation]

# Tech tracking
tech-stack:
  added: []
  patterns: [skipif-gated integration tests for generated data files]

key-files:
  created:
    - tests/integration/test_output_separation.py
  modified:
    - .github/workflows/rdfgeneration.yml
    - .github/workflows/Turtle_File_Quality_Control.yml

key-decisions:
  - "Tests use ENRICHED_OBJECT_PREFIXES list to detect cross-reference triples rather than checking all owl:sameAs"
  - "Combined triple count regression threshold set at 150,000 based on current output estimates"

patterns-established:
  - "pytest.mark.skipif gating for tests that depend on generated data files"
  - "Namespace prefix list for identifying enrichment cross-references vs entity descriptions"

requirements-completed: [SEP-01, SEP-02, SEP-03]

# Metrics
duration: 1min
completed: 2026-03-08
---

# Phase 4 Plan 3: CI Workflow and Integration Test Summary

**Updated rdfgeneration and QC workflows to validate four TTL files; created 7 pytest integration tests for separation invariants**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-08T16:01:26Z
- **Completed:** 2026-03-08T16:02:48Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added AOPWikiRDF-Enriched.ttl to rdfgeneration.yml expected_files validation list
- Added AOPWikiRDF-Enriched.ttl to QC workflow turtle validation command
- Created 7 integration tests covering pure file cross-ref absence, enriched file validity, VoID subsets/licensing/provenance/examples, and combined triple count regression

## Task Commits

Each task was committed atomically:

1. **Task 1: Update GitHub Actions workflows for four-file output** - `ac46959` (feat)
2. **Task 2: Create integration tests for output separation** - `8e1b9b1` (test)

## Files Created/Modified
- `.github/workflows/rdfgeneration.yml` - Added AOPWikiRDF-Enriched.ttl to expected_files list
- `.github/workflows/Turtle_File_Quality_Control.yml` - Added enriched file to validation command
- `tests/integration/test_output_separation.py` - 7 integration tests for separation verification

## Decisions Made
- Tests check for specific cross-reference namespace prefixes (CHEBI, ChEMBL, DrugBank, etc.) rather than all owl:sameAs triples, since UniProt owl:sameAs in gene identifier sections stays in the pure file
- Combined triple count regression threshold set at 150,000 as a conservative floor

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CI workflows ready to validate four-file output on next production run
- Integration tests will skip gracefully until data files are generated with the new separation
- Phase 4 output separation plans complete; ready for Phase 5 validation

---
*Phase: 04-output-separation*
*Completed: 2026-03-08*
