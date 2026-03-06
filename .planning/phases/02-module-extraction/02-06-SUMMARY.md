---
phase: 02-module-extraction
plan: 06
subsystem: testing
tags: [regression-test, ntriples-diff, triple-parity, rdflib]
dependency_graph:
  requires:
    - 02-05
  provides:
    - triple-for-triple regression test comparing modularized vs monolith output
  affects: [future-refactoring, phase-03]
tech_stack:
  added: []
  patterns: [sorted-ntriples-diff, blank-node-normalization, file-uri-normalization]
key_files:
  created:
    - tests/integration/test_regression.py
  modified:
    - src/aopwiki_rdf/pipeline_monolith.py
decisions:
  - "Normalize file:// URIs, blank nodes, ISO dates, and ctime dates before NTriples comparison"
  - "Remove redundant local import time in monolith to fix UnboundLocalError scoping bug"
requirements_completed: [MOD-07]
metrics:
  duration_minutes: 52
  completed: "2026-03-06T18:20:00Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 2 Plan 6: Regression Test Summary

**Sorted NTriples regression test validates triple-for-triple parity between monolith and modularized pipeline across all three RDF output files**

## Performance

- **Duration:** 52 min (includes two full pipeline runs at ~19 min each)
- **Started:** 2026-03-06T17:28:42Z
- **Completed:** 2026-03-06T18:20:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Regression test validates modularized pipeline produces identical RDF output to monolith
- All three output files match: AOPWikiRDF.ttl (131K+ triples), AOPWikiRDF-Genes.ttl, AOPWikiRDF-Void.ttl
- Normalization handles blank nodes, file:// URIs with temp paths, ISO and ctime date formats
- Test is reusable for future refactoring phases (marked @pytest.mark.slow, runnable standalone)
- Fixed scoping bug in pipeline_monolith.py (redundant local `import time` caused UnboundLocalError)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create regression test** - `ce799f7` (test)
2. **Task 2: Run and fix regression test** - `fce383d` (fix: monolith scoping bug), `42efa35` (test: normalization fixes)

## Files Created/Modified
- `tests/integration/test_regression.py` - Triple-for-triple regression test with NTriples normalization
- `src/aopwiki_rdf/pipeline_monolith.py` - Fixed `import time` scoping bug (redundant local import removed)

## Decisions Made
- Normalize file:// URIs by replacing temp directory paths with placeholder (BiologicalEvent entities use data_dir as base URI)
- Normalize both ISO datetime and ctime-format dates in VoID file comparison
- Remove redundant `import time` inside main() rather than adding another local import

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed UnboundLocalError for time module in pipeline_monolith.py**
- **Found during:** Task 2 (running regression test)
- **Issue:** Redundant `import time` at line 1901 inside main() caused Python to treat `time` as local variable throughout the function, making line 1065 (`time.ctime(...)`) fail with UnboundLocalError
- **Fix:** Removed redundant local `import time` at line 1901; module-level import at line 16 now works correctly
- **Files modified:** src/aopwiki_rdf/pipeline_monolith.py
- **Verification:** Monolith pipeline runs successfully
- **Committed in:** fce383d

**2. [Rule 1 - Bug] Fixed normalization missing file:// URIs and ctime dates**
- **Found during:** Task 2 (first regression test run showed 10,154 false diffs)
- **Issue:** BiologicalEvent URIs embed temp dir path (file:///tmp/regression_mono_xxx/), VoID importedOn uses ctime format ("Fri Mar  6 18:31:31 2026") -- neither caught by original regex
- **Fix:** Added _FILE_URI_RE for file:// URI normalization, _CTIME_RE for ctime-format dates, improved ISO date regex
- **Files modified:** tests/integration/test_regression.py
- **Verification:** Second regression run passes with all three files matching
- **Committed in:** 42efa35

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
- First regression run failed due to monolith scoping bug (not a modularization issue)
- 10,154 triple diffs were all false positives from temp dir paths in file:// URIs -- zero actual content differences

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 2 acceptance gate PASSED: modularized pipeline produces identical RDF output to monolith
- Regression test available at tests/integration/test_regression.py for future refactoring validation
- Monolith preserved as pipeline_monolith.py for reference and regression baseline

---
*Phase: 02-module-extraction*
*Completed: 2026-03-06*
