---
phase: 02-module-extraction
plan: 05
subsystem: pipeline-orchestrator
tags: [orchestrator, refactoring, module-wiring]
dependency_graph:
  requires: [02-01, 02-02, 02-03, 02-04]
  provides: [thin-orchestrator, monolith-preservation]
  affects: [run_conversion.py, regression-testing]
tech_stack:
  added: []
  patterns: [staged-coordinator, context-dict-data-flow]
key_files:
  created:
    - src/aopwiki_rdf/pipeline_monolith.py
    - tests/unit/test_orchestrator.py
  modified:
    - src/aopwiki_rdf/pipeline.py
decisions:
  - Orchestrator parses XML separately from parser module to provide xml_root to mapping stages (ParsedEntities lacks root/ns fields)
  - Chemical identifier lists (listofcas, listofinchikey, listofcomptox) reconstructed from chedict since ParsedEntities does not expose them
  - parse_aopwiki_xml called with config=None to skip internal promapping, deferring to protein_ontology module
metrics:
  duration_minutes: 8
  completed: "2026-03-06T15:35:00Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 2 Plan 5: Orchestrator Replacement Summary

Replaced the 2,334-line monolith pipeline.py with a 392-line staged orchestrator that wires all extracted modules through a context dict with 8 named stages, timing, and logging.

## What Was Done

### Task 1: Rename monolith and create thin orchestrator
- Copied pipeline.py (2,334 lines) to pipeline_monolith.py for regression testing in Plan 06
- Rewrote pipeline.py as thin orchestrator with 8 stages: Setup, XML Parse, Chemical Mapping, Protein Ontology, HGNC Gene Mapping, Write AOP RDF, Write Genes RDF, Write VoID RDF
- All data flows through a context dict passed between stages; no shared mutable globals
- main(config) API preserved -- run_conversion.py works unchanged
- Stages respect data dependency ordering: parse before mapping, all mapping before writing
- Variable shadowing resolved: protein ontology lists stored as pro_hgnclist (distinct from gene mapping hgnclist)
- Commit: dcf06a1

### Task 2: Add unit tests for orchestrator
- 8 structural tests verifying: API signature, module imports, no exec(), line count <400, monolith >2000 lines, stage definitions, context dict pattern
- Commit: 524af3d

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ParsedEntities missing xml_root and aopxml_ns fields**
- **Found during:** Task 1
- **Issue:** The plan's interface section listed xml_root and aopxml_ns as ParsedEntities fields, but the actual dataclass lacks them. Mapping functions (map_genes_in_entities, map_chemicals) require xml_root.
- **Fix:** Orchestrator imports AOPXML_NS constant from parser module and parses XML separately to get root, then passes both to mapping stages.
- **Files modified:** src/aopwiki_rdf/pipeline.py

**2. [Rule 3 - Blocking] Chemical identifier lists not exposed by ParsedEntities**
- **Found during:** Task 1
- **Issue:** listofcas, listofinchikey, listofcomptox are built during XML parsing but not included in ParsedEntities. The RDF writer needs them.
- **Fix:** Orchestrator reconstructs these lists from chedict property values (dc:identifier for CAS, cheminf:000059 for InChIKey, cheminf:000568 for CompTox).
- **Files modified:** src/aopwiki_rdf/pipeline.py

## Verification Results

- `from aopwiki_rdf.pipeline import main` -- passes
- `pytest tests/unit/test_orchestrator.py` -- 8/8 pass
- `import run_conversion` -- CLI wrapper OK
- pipeline.py: 392 lines (under 400 limit)
- pipeline_monolith.py: 2,334 lines preserved

## Self-Check: PASSED

- pipeline.py: FOUND
- pipeline_monolith.py: FOUND
- test_orchestrator.py: FOUND
- Commit dcf06a1: FOUND
- Commit 524af3d: FOUND
