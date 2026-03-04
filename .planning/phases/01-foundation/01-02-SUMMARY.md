---
phase: 01-foundation
plan: 02
subsystem: parser
tags: [xml-parsing, dataclass, elementtree, tdd]

# Dependency graph
requires:
  - phase: 01-01
    provides: PipelineConfig dataclass, utils.py helpers, parser/ placeholder
provides:
  - ParsedEntities dataclass with 13 entity dictionaries
  - Standalone parse_aopwiki_xml() function importable without side effects
  - Chemical mapping functions (map_chemicals_batch, parse_batch_chemical_response, map_chemical_individual_fallback)
  - Sample AOP-Wiki XML fixture for testing
  - Unit tests covering import safety, return types, attribute presence
affects: [01-03, 02-rdf-writer, 02-gene-mapping]

# Tech tracking
tech-stack:
  added: []
  patterns: [tdd-red-green, dataclass-entity-container, config-optional-for-offline-parsing]

key-files:
  created:
    - src/aopwiki_rdf/parser/xml_parser.py
    - tests/fixtures/sample_aopwiki.xml
    - tests/unit/test_xml_parser.py
    - tests/conftest.py
  modified:
    - src/aopwiki_rdf/parser/__init__.py
    - .gitignore

key-decisions:
  - "Config is optional for parse_aopwiki_xml: when None, BridgeDb and promapping network calls are skipped, enabling offline testing"
  - "celldict and organdict are populated from KE cell-term/organ-term data for standalone access alongside kedict embedding"

patterns-established:
  - "ParsedEntities dataclass: single typed return object for all parser output"
  - "TDD workflow: RED tests first, then GREEN implementation"
  - "No network calls without explicit config: parser works offline by default"

requirements-completed: [MOD-02]

# Metrics
duration: 4min
completed: 2026-03-04
---

# Phase 1 Plan 2: XML Parser Extraction Summary

**Standalone XML parser module extracting ~700 lines from monolith into parse_aopwiki_xml() returning typed ParsedEntities dataclass with all 13 entity dictionaries**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-04T18:25:45Z
- **Completed:** 2026-03-04T18:30:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Extracted XML parsing logic from monolith lines 347-1201 into standalone module
- ParsedEntities dataclass with all 13 entity dictionaries matching monolith names
- Chemical mapping functions included (tightly coupled to parsing in Phase 1)
- 6 unit tests all passing with TDD red-green workflow
- Parser importable without any network calls or side effects

## Task Commits

Each task was committed atomically:

1. **Task 1: Create sample XML fixture and parser unit tests** - `7bc9722` (test)
2. **Task 2: Extract XML parser module from monolith** - `90db592` (feat)

## Files Created/Modified
- `src/aopwiki_rdf/parser/xml_parser.py` - Standalone XML parser with ParsedEntities dataclass and chemical mapping functions
- `src/aopwiki_rdf/parser/__init__.py` - Updated exports for parse_aopwiki_xml and ParsedEntities
- `tests/fixtures/sample_aopwiki.xml` - Minimal structurally valid AOP-Wiki XML fixture
- `tests/unit/test_xml_parser.py` - 6 unit tests for parser module
- `tests/conftest.py` - Shared pytest fixture for sample XML path
- `.gitignore` - Fixed test_*.py pattern to allow files inside tests/ directory

## Decisions Made
- **Config optional for offline parsing**: parse_aopwiki_xml() accepts optional PipelineConfig. When None, BridgeDb chemical mapping and protein ontology download are skipped. This enables testing without network dependencies.
- **celldict/organdict as separate attributes**: Cell-term and organ-term data is stored both inside kedict (matching monolith behavior) and in standalone celldict/organdict attributes for future standalone access.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed .gitignore blocking test files in tests/ directory**
- **Found during:** Task 1
- **Issue:** Root-level `test_*.py` and `debug_*.py` patterns in .gitignore were preventing git add of tests/unit/test_xml_parser.py
- **Fix:** Changed patterns to `/test_*.py` and `/debug_*.py` (root-only) so tests/ directory files are not ignored
- **Files modified:** .gitignore
- **Committed in:** 7bc9722 (Task 1 commit)

**2. [Rule 1 - Bug] Added null check for background text in AOP parsing**
- **Found during:** Task 2
- **Issue:** Monolith accesses `AOP.find(aopxml + 'background').text` without checking if text is None, which could cause AttributeError on elements with no text content
- **Fix:** Added `if AOP.find(aopxml + 'background').text is not None` guard before accessing text
- **Files modified:** src/aopwiki_rdf/parser/xml_parser.py
- **Committed in:** 90db592 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Minor fixes for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed items documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Parser module ready for Plan 03 (HGNC gene mapping extraction)
- ParsedEntities provides typed interface for Phase 2 RDF writer module
- Chemical mapping functions included in parser for now, to be separated in Phase 2

---
*Phase: 01-foundation*
*Completed: 2026-03-04*
