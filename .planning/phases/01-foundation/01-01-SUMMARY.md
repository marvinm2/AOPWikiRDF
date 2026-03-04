---
phase: 01-foundation
plan: 01
subsystem: infra
tags: [python-packaging, dataclass, pyproject-toml, pipeline-config]

# Dependency graph
requires: []
provides:
  - PipelineConfig dataclass with 9 fields and production defaults
  - src/aopwiki_rdf/ package installable via pip install -e .
  - Clean run_conversion.py using import-and-call pattern (no exec)
  - Extracted utils.py with safe_get_text, clean_html_tags, download_with_retry
  - Empty parser/ and hgnc/ subpackage placeholders for Plans 02 and 03
affects: [01-02, 01-03, 02-rdf-writer, 02-gene-mapping]

# Tech tracking
tech-stack:
  added: [pyproject.toml, setuptools-build-meta]
  patterns: [dataclass-config, src-layout-package, import-and-call-entry-point]

key-files:
  created:
    - src/aopwiki_rdf/__init__.py
    - src/aopwiki_rdf/config.py
    - src/aopwiki_rdf/pipeline.py
    - src/aopwiki_rdf/utils.py
    - src/aopwiki_rdf/parser/__init__.py
    - src/aopwiki_rdf/hgnc/__init__.py
    - pyproject.toml
  modified:
    - run_conversion.py
    - .github/workflows/rdfgeneration.yml

key-decisions:
  - "Transitional exec in pipeline.py: main(config) API is clean but internally execs the monolith with replaced constants. Removed in Phase 2."
  - "pyproject.toml uses setuptools build_meta backend with PEP 621 metadata"

patterns-established:
  - "PipelineConfig dataclass: single typed config object replacing module-level constants"
  - "src/ layout: all package code under src/aopwiki_rdf/ to prevent accidental imports"
  - "No module-level side effects: logging, network, filesystem only in functions"

requirements-completed: [MOD-01]

# Metrics
duration: 3min
completed: 2026-03-04
---

# Phase 1 Plan 1: Package Scaffold Summary

**PipelineConfig dataclass with src/ package layout replacing exec()-based config injection in run_conversion.py**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-04T18:20:09Z
- **Completed:** 2026-03-04T18:23:31Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Created src/aopwiki_rdf/ package with pyproject.toml for editable install
- PipelineConfig dataclass with 9 fields matching all production constants
- Rewrote run_conversion.py to use clean import-and-call pattern (zero exec calls)
- Extracted helper functions to utils.py with no module-level side effects
- Updated GitHub Actions workflow with pip install -e . step

## Task Commits

Each task was committed atomically:

1. **Task 1: Create package scaffold with PipelineConfig and utils** - `d474b5c` (feat)
2. **Task 2: Create pipeline.py main() and rewrite run_conversion.py** - `6aabd1e` (feat)

## Files Created/Modified
- `pyproject.toml` - PEP 621 package metadata for pip install -e .
- `src/aopwiki_rdf/__init__.py` - Package root with version string
- `src/aopwiki_rdf/config.py` - PipelineConfig dataclass with 9 production-default fields
- `src/aopwiki_rdf/pipeline.py` - main(config) entry point (transitional monolith wrapper)
- `src/aopwiki_rdf/utils.py` - Extracted helpers: safe_get_text, clean_html_tags, download_with_retry, validation functions
- `src/aopwiki_rdf/parser/__init__.py` - Empty placeholder for Plan 02
- `src/aopwiki_rdf/hgnc/__init__.py` - Empty placeholder for Plan 03
- `run_conversion.py` - Rewritten: imports main() and passes PipelineConfig
- `.github/workflows/rdfgeneration.yml` - Added pip install -e . step

## Decisions Made
- **Transitional exec approach**: pipeline.py main() presents a clean public API but internally still execs the monolith with string-replaced constants. This is pragmatic for Phase 1 -- the 2000-line monolith body will be decomposed module-by-module in Phase 2 Plans. The public contract (run_conversion.py calls main(config)) is correct from day one.
- **setuptools build_meta**: Used standard PEP 517 backend rather than setuptools legacy backend.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed pyproject.toml build backend**
- **Found during:** Task 1 (package scaffold)
- **Issue:** Initial build-backend `setuptools.backends._legacy:_Backend` does not exist in current setuptools
- **Fix:** Changed to `setuptools.build_meta` (standard PEP 517 backend)
- **Files modified:** pyproject.toml
- **Verification:** pip install -e . succeeds
- **Committed in:** d474b5c (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor configuration fix, no scope impact.

## Issues Encountered
None beyond the build backend fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Package scaffold ready for Plan 02 (XML parser extraction into parser/ subpackage)
- Package scaffold ready for Plan 03 (HGNC dynamic download into hgnc/ subpackage)
- run_conversion.py public API is stable -- all future work is internal to the package

---
*Phase: 01-foundation*
*Completed: 2026-03-04*
