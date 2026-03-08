---
phase: 04-output-separation
plan: 01
subsystem: rdf
tags: [turtle, owl-sameAs, cross-reference, provenance, rdf-writer]

# Dependency graph
requires:
  - phase: 02-module-extraction
    provides: modular writer.py with write_aop_rdf, namespaces.py with prefix constants
provides:
  - ENRICHED_PREFIXES constant for AOPWikiRDF-Enriched.ttl
  - write_enriched_rdf function for cross-reference triple output
  - write_aop_rdf cleaned of enrichment cross-references
affects: [04-02, 04-03, 05-validation]

# Tech tracking
tech-stack:
  added: []
  patterns: [file-level provenance separation for pure vs enriched RDF]

key-files:
  created: []
  modified:
    - src/aopwiki_rdf/rdf/namespaces.py
    - src/aopwiki_rdf/rdf/writer.py

key-decisions:
  - "Enriched file emits ONLY owl:sameAs (+ optional skos:exactMatch) -- no type declarations or base properties"
  - "Mapped identifier sections (chemical/gene entity descriptions) remain in write_aop_rdf as they describe entities, not cross-references"
  - "UniProt owl:sameAs in mapped gene identifiers section stays in write_aop_rdf (entity self-description, not enrichment)"

patterns-established:
  - "Enriched writer receives enrichment_data dict with chedict/bioobjdict/prodict keys"
  - "ENRICHED_PREFIXES follows same hardcoded string pattern as GENES_PREFIXES/VOID_PREFIXES"

requirements-completed: [SEP-01, SEP-02]

# Metrics
duration: 2min
completed: 2026-03-08
---

# Phase 4 Plan 1: Output Separation Summary

**Split write_aop_rdf into pure source-only writer and write_enriched_rdf for owl:sameAs cross-reference triples with dedicated ENRICHED_PREFIXES**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-08T15:57:56Z
- **Completed:** 2026-03-08T15:59:35Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added ENRICHED_PREFIXES constant with all 18 namespace prefixes needed for cross-reference triples
- Created write_enriched_rdf function that emits chemical and protein ontology cross-references to separate file
- Removed chemical owl:sameAs/skos:exactMatch and protein ontology owl:sameAs from write_aop_rdf

## Task Commits

Each task was committed atomically:

1. **Task 1: Add ENRICHED_PREFIXES constant to namespaces.py** - `5bdeb70` (feat)
2. **Task 2: Split write_aop_rdf and create write_enriched_rdf** - `3d0c918` (feat)

## Files Created/Modified
- `src/aopwiki_rdf/rdf/namespaces.py` - Added ENRICHED_PREFIXES constant between GENES_PREFIXES and VOID_PREFIXES
- `src/aopwiki_rdf/rdf/writer.py` - Removed cross-ref emission from write_aop_rdf, added write_enriched_rdf function

## Decisions Made
- Enriched file emits only cross-reference predicates (owl:sameAs, optionally skos:exactMatch) with no type declarations or base properties on subjects
- Mapped chemical/gene identifier sections remain in write_aop_rdf since they describe entities that exist as cross-reference targets
- UniProt owl:sameAs in mapped gene identifiers section stays in write_aop_rdf (entity self-description)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- write_enriched_rdf ready to be called from orchestrator/pipeline
- Pipeline integration (04-02) can now wire enrichment_data dict and call write_enriched_rdf
- VoID metadata update (04-03) can add AOPWikiRDF-Enriched.ttl dataset description

---
*Phase: 04-output-separation*
*Completed: 2026-03-08*
