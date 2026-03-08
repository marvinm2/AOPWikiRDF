---
phase: 03-predicate-correction
plan: 02
subsystem: rdf-writer
tags: [owl-sameAs, skos-exactMatch, dual-predicate, rdfs-label, hgnc-numeric]

# Dependency graph
requires:
  - phase: 03-predicate-correction
    provides: Numeric HGNC ID keyed gene dicts and symbol_lookup from Plan 01
provides:
  - owl:sameAs at all 3 cross-database identifier emission sites
  - Dual-predicate transition flag (emit_legacy_predicates) for backward compatibility
  - rdfs:label with gene symbols on gene nodes in both main and Genes RDF
  - Pipeline wiring of config and symbol_lookup to writer functions
affects: [03-03 SNORQL audit queries, 04 regression test expected output]

# Tech tracking
tech-stack:
  added: []
  patterns: [dual-predicate-emission, configurable-rdf-output]

key-files:
  created: []
  modified:
    - src/aopwiki_rdf/config.py
    - src/aopwiki_rdf/rdf/writer.py
    - src/aopwiki_rdf/pipeline.py
    - tests/unit/test_rdf_writer.py

key-decisions:
  - "config=None defaults to owl:sameAs only (correct predicate) for safe backward compatibility"
  - "rdfs:label uses symbol_lookup.get(numeric_id, numeric_id) fallback to numeric ID when symbol unavailable"

patterns-established:
  - "Dual-predicate emission: config.emit_legacy_predicates controls skos:exactMatch presence"
  - "Gene label pattern: symbol_lookup flows from gene_mapper through pipeline context to writer"

requirements-completed: [PRED-01, PRED-04]

# Metrics
duration: 5min
completed: 2026-03-08
---

# Phase 3 Plan 02: Predicate Correction Summary

**Replaced skos:exactMatch with owl:sameAs at 3 emission sites, added dual-predicate transition flag, and rdfs:label with gene symbols on gene nodes**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-08T08:29:44Z
- **Completed:** 2026-03-08T08:35:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- All 3 skos:exactMatch sites (protein ontology, chemical identifiers, gene identifiers) converted to conditional dual-predicate emission
- emit_legacy_predicates config flag controls backward compatibility during downstream consumer migration
- Gene nodes have rdfs:label with human-readable symbol from symbol_lookup
- Gene URIs use numeric HGNC IDs (hgnc:1100 not hgnc:BRCA1)
- Pipeline wires config and symbol_lookup to both writer functions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add emit_legacy_predicates config flag and update writer predicate emission** - `8f1dc91` (test: failing tests), `3d5c3da` (feat: implementation)
2. **Task 2: Wire config and symbol_lookup through pipeline to writer functions** - `3e4e0e0` (feat)

## Files Created/Modified
- `src/aopwiki_rdf/config.py` - Added emit_legacy_predicates field (default True)
- `src/aopwiki_rdf/rdf/writer.py` - Dual-predicate emission at 3 sites, rdfs:label on gene nodes, config parameter on both writer functions
- `src/aopwiki_rdf/pipeline.py` - Passes config and symbol_lookup to write_aop_rdf and write_genes_rdf
- `tests/unit/test_rdf_writer.py` - 13 new tests for predicates, gene labels, numeric URIs, Turtle validity

## Decisions Made
- When config is None (backward compatibility), emit only owl:sameAs -- the semantically correct predicate
- rdfs:label falls back to numeric ID string when symbol_lookup has no entry for a given HGNC ID
- Updated existing test_write_genes_rdf_minimal to use numeric HGNC IDs (hgnc:11998 for TP53)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All predicate corrections in place with dual-predicate transition support
- Gene labels queryable via rdfs:label
- Ready for Phase 4 regression test updates (output format intentionally changed)

## Self-Check: PASSED

All 4 modified files exist. All 3 commit hashes verified.

---
*Phase: 03-predicate-correction*
*Completed: 2026-03-08*
