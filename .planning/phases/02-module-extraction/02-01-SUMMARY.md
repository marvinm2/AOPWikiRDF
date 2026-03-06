---
phase: 02-module-extraction
plan: 01
subsystem: api
tags: [bridgedb, protein-ontology, rdf, namespaces, batch-api]

requires:
  - phase: 01-foundation
    provides: pipeline.py monolith with config/utils extracted
provides:
  - mapping/ package with BridgeDb batch client (gene + chemical)
  - mapping/ package with protein ontology promapping parser
  - rdf/ package with namespace/prefix constants
affects: [02-02, 02-03, 02-04, 02-05, 02-06]

tech-stack:
  added: []
  patterns: [generic-batch-with-fallback, domain-specific-wrappers, prefixed-id-stripping]

key-files:
  created:
    - src/aopwiki_rdf/mapping/__init__.py
    - src/aopwiki_rdf/mapping/bridgedb.py
    - src/aopwiki_rdf/mapping/protein_ontology.py
    - src/aopwiki_rdf/rdf/__init__.py
    - src/aopwiki_rdf/rdf/namespaces.py
  modified: []

key-decisions:
  - "Generic batch_xrefs pattern factored from gene/chemical implementations with parse_fn + fallback_fn injection"
  - "Protein ontology return keys prefixed pro_ (pro_hgnclist) to prevent confusion with gene-mapping hgnclist"
  - "GENES_PREFIXES and VOID_PREFIXES stored as exact string constants to guarantee byte-identical output"

patterns-established:
  - "Generic batch with fallback: batch_xrefs(identifiers, url, system_code, parse_fn, fallback_fn) pattern for any BridgeDb endpoint"
  - "Domain wrapper pattern: batch_xrefs_gene/batch_xrefs_chemical wrap generic with domain-specific parse and fallback"
  - "Explicit parameter passing: no module globals, all config passed as function arguments"

requirements-completed: [MOD-03, MOD-04, MOD-05]

duration: 3min
completed: 2026-03-06
---

# Phase 02 Plan 01: Shared Leaf Modules Summary

**BridgeDb batch client (gene + chemical), protein ontology mapper, and RDF namespace constants extracted as independent importable modules**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-06T15:01:30Z
- **Completed:** 2026-03-06T15:04:17Z
- **Tasks:** 2
- **Files created:** 5

## Accomplishments
- Extracted BridgeDb batch xref logic into a generic function with gene and chemical domain wrappers
- Extracted protein ontology promapping.txt download and parsing with clear naming to avoid variable shadowing
- Extracted all three RDF prefix blocks (main from CSV, genes hardcoded, VoID hardcoded) plus individual NS_* constants

## Task Commits

Each task was committed atomically:

1. **Task 1: Create mapping and rdf package scaffolds with BridgeDb client** - `dacc52d` (feat)
2. **Task 2: Extract protein ontology mapper and RDF namespaces** - `c5724f9` (feat)

## Files Created/Modified
- `src/aopwiki_rdf/mapping/__init__.py` - Package marker for mapping subpackage
- `src/aopwiki_rdf/mapping/bridgedb.py` - Generic batch xref + gene/chemical wrappers with system code mappings
- `src/aopwiki_rdf/mapping/protein_ontology.py` - promapping.txt download, parse, and identifier extraction
- `src/aopwiki_rdf/rdf/__init__.py` - Package marker for rdf subpackage
- `src/aopwiki_rdf/rdf/namespaces.py` - get_main_prefixes, GENES_PREFIXES, VOID_PREFIXES, NS_* constants

## Decisions Made
- Factored generic `batch_xrefs` from two separate implementations to reduce duplication; gene and chemical wrappers inject their own parse and fallback functions
- Named protein ontology return keys with `pro_` prefix (pro_hgnclist, pro_uniprotlist, pro_ncbigenelist) to prevent name collision with gene-mapping hgnclist in the orchestrator
- Kept GENES_PREFIXES and VOID_PREFIXES as exact string constants (not generated from data) to ensure byte-identical RDF output during migration

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- mapping/ and rdf/ packages ready for Plans 02-06 to import
- BridgeDb client ready for gene mapper (02-02) and chemical mapper (02-03)
- Protein ontology mapper ready for orchestrator (02-06)
- RDF namespaces ready for RDF writer (02-04)
- No circular imports between mapping/ and rdf/

---
*Phase: 02-module-extraction*
*Completed: 2026-03-06*
