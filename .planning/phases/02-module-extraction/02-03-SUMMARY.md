---
phase: 02-module-extraction
plan: 03
subsystem: mapping
tags: [bridgedb, chemical-mapping, cas, batch-api, cheminf]

requires:
  - phase: 01-foundation
    provides: "Package structure with parser/xml_parser.py containing chemical functions"
provides:
  - "Standalone chemical_mapper.py with map_chemicals() for BridgeDb CAS cross-references"
  - "Cleaned parser/xml_parser.py without duplicate chemical mapping functions"
affects: [02-module-extraction, pipeline-integration]

tech-stack:
  added: []
  patterns: ["Lazy import for cross-module dependency (parser imports mapper at call site)"]

key-files:
  created:
    - src/aopwiki_rdf/mapping/chemical_mapper.py
    - tests/unit/test_chemical_mapper.py
  modified:
    - src/aopwiki_rdf/parser/xml_parser.py

key-decisions:
  - "Used lazy import in parser to avoid circular dependency between parser and mapping packages"
  - "Chemical mapper reads CAS from chedict cheminf:000446 property rather than re-parsing XML"

patterns-established:
  - "mapping/ package pattern: public map_* function with private _batch/_parse/_fallback helpers"

requirements-completed: [MOD-04]

duration: 4min
completed: 2026-03-06
---

# Phase 2 Plan 3: Chemical Mapper Extraction Summary

**Standalone chemical mapper module with BridgeDb batch CAS-to-identifier cross-referencing, consolidated from duplicate implementations in parser and pipeline**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-06T15:01:49Z
- **Completed:** 2026-03-06T15:05:34Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Extracted chemical_mapper.py with map_chemicals() as single authoritative BridgeDb chemical mapping function
- Removed 220+ lines of duplicate chemical mapping code from parser/xml_parser.py
- Parser now delegates to mapping.chemical_mapper via lazy import, keeping both modules independently importable
- Unit tests pass with real BridgeDb API (Bisphenol A, Formaldehyde)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract chemical mapper and clean parser module** - `a3b0695` (feat)
2. **Task 2: Add unit tests for chemical mapper** - `9dde8f9` (test)

## Files Created/Modified
- `src/aopwiki_rdf/mapping/chemical_mapper.py` - Standalone chemical BridgeDb batch mapping with map_chemicals() public API
- `src/aopwiki_rdf/parser/xml_parser.py` - Removed 3 duplicate chemical functions, added lazy import delegation
- `tests/unit/test_chemical_mapper.py` - Unit tests: importability, empty input, live BridgeDb integration

## Decisions Made
- Used lazy import (`from ... import` inside function body) in parser to call chemical_mapper at runtime, avoiding circular dependency between parser and mapping packages
- Chemical mapper reads CAS numbers from chedict's `cheminf:000446` property rather than re-iterating XML, since the parser already populates this field

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused requests import from parser**
- **Found during:** Task 1 (parser cleanup)
- **Issue:** After removing chemical mapping functions, the `import requests` at module level was unused
- **Fix:** Removed the import line to keep the module clean
- **Files modified:** src/aopwiki_rdf/parser/xml_parser.py
- **Verification:** Module imports successfully without requests
- **Committed in:** a3b0695 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial cleanup, no scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- mapping/ package now has chemical_mapper.py ready for use by pipeline integration
- BridgeDb batch client functions are consolidated in one place
- Parser module is cleaner and focused on XML parsing only

---
*Phase: 02-module-extraction*
*Completed: 2026-03-06*
