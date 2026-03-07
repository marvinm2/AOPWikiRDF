---
phase: 03-predicate-correction
plan: 01
subsystem: mapping
tags: [hgnc, gene-mapper, bridgedb, numeric-id]

# Dependency graph
requires:
  - phase: 02-module-extraction
    provides: Modular gene_mapper.py with build_gene_dicts, _map_genes_in_text, build_gene_xrefs
provides:
  - Numeric HGNC ID keyed gene dicts (genedict1, genedict2)
  - symbol_lookup dict mapping numeric ID to gene symbol
  - symbol_lookup wired through pipeline context as gene_symbol_lookup
affects: [03-02 writer predicate changes, 03-03 protein ontology numeric IDs]

# Tech tracking
tech-stack:
  added: []
  patterns: [numeric-hgnc-id-keying, symbol-lookup-reverse-mapping]

key-files:
  created: []
  modified:
    - src/aopwiki_rdf/mapping/gene_mapper.py
    - src/aopwiki_rdf/pipeline.py
    - tests/unit/test_gene_mapper.py
    - tests/unit/test_enhanced_precision.py

key-decisions:
  - "Keep BridgeDb system code H (symbol) with symbol_lookup reverse mapping instead of switching to Hac (accession)"
  - "False positive Filter 4 matches on alias text instead of gene dict key for numeric-key compatibility"

patterns-established:
  - "Numeric HGNC ID keying: all gene dicts use numeric string keys (e.g. '5' not 'A1BG')"
  - "Symbol lookup pattern: symbol_lookup dict flows through pipeline context for downstream stages"

requirements-completed: [PRED-02, GENE-03, GENE-04]

# Metrics
duration: 4min
completed: 2026-03-07
---

# Phase 3 Plan 01: Gene Mapper Re-keying Summary

**Re-keyed gene mapper internal dicts from symbol to numeric HGNC ID with symbol_lookup reverse mapping for BridgeDb queries**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-07T08:38:27Z
- **Completed:** 2026-03-07T08:43:10Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- build_gene_dicts returns 3-tuple with numeric-keyed genedict1, genedict2, and symbol_lookup
- _map_genes_in_text automatically produces hgnc:NNNN format IDs (no code change needed)
- BridgeDb queries use symbol_lookup to convert numeric IDs back to symbols for proven H system code
- Three-stage false positive filtering preserved and tested with numeric-keyed dicts
- Pipeline wired to pass symbol_lookup through context for writer stage (Plan 02)

## Task Commits

Each task was committed atomically:

1. **Task 1: Re-key build_gene_dicts to numeric HGNC IDs** - `f9d7e99` (test: failing tests), `5957964` (feat: implementation)
2. **Task 2: Update pipeline.py to pass symbol_lookup** - `3dd6aa4` (feat)

## Files Created/Modified
- `src/aopwiki_rdf/mapping/gene_mapper.py` - Re-keyed dicts, symbol_lookup return, BridgeDb symbol conversion
- `src/aopwiki_rdf/pipeline.py` - 3-value unpack, symbol_lookup in context
- `tests/unit/test_gene_mapper.py` - Updated for numeric keys, 3-tuple return, symbol_lookup
- `tests/unit/test_enhanced_precision.py` - Updated to use module function with numeric-keyed dicts

## Decisions Made
- Kept BridgeDb system code 'H' (symbol) with symbol_lookup reverse mapping -- proven in production, avoids API migration risk
- Updated _is_false_positive Filter 4 to match on alias text (matched_alias) instead of gene dict key -- necessary since keys are now numeric, but Filters 1-3 already catch all known false positives
- Used re.compile pattern to validate HGNC:NNNN format in column 0, logging and skipping invalid lines

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated _is_false_positive gene-specific filters for numeric keys**
- **Found during:** Task 1 (gene mapper re-keying)
- **Issue:** Filter 4 checked `gene_symbol == 'IV'` and `gene_symbol == 'GCNT2'` which would never match numeric keys
- **Fix:** Changed to check `stripped == 'IV'` and `stripped == 'II'` (matching on alias text)
- **Files modified:** src/aopwiki_rdf/mapping/gene_mapper.py
- **Verification:** False positive filtering tests pass identically
- **Committed in:** 5957964 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Essential for correctness -- gene-specific filters would silently fail without this fix. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Gene dicts are now keyed by numeric HGNC ID -- foundation for correct hgnc:NNNN URIs in writer
- symbol_lookup available in pipeline context (gene_symbol_lookup) for rdfs:label generation in Plan 02
- BridgeDb xref resolution confirmed working with symbol-based queries via lookup

---
*Phase: 03-predicate-correction*
*Completed: 2026-03-07*
