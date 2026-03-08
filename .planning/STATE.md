---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 03-02-PLAN.md
last_updated: "2026-03-08T09:03:15.051Z"
last_activity: 2026-03-08 — Completed 03-03 SNORQL audit
progress:
  total_phases: 5
  completed_phases: 3
  total_plans: 13
  completed_plans: 13
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-04)

**Core value:** Produce accurate, well-structured RDF from AOP-Wiki XML every week — reliably and with traceable provenance for pure vs enriched content.
**Current focus:** Phase 3 — Predicate Correction

## Current Position

Phase: 3 of 5 (Predicate Correction)
Plan: 3 of 3 in current phase (all complete)
Status: Phase 3 complete
Last activity: 2026-03-08 — Completed 03-02 predicate correction

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01 P01 | 3 | 2 tasks | 9 files |
| Phase 01 P02 | 4 | 2 tasks | 6 files |
| Phase 01 P03 | 2 | 2 tasks | 6 files |
| Phase 02 P02 | 4 | 2 tasks | 3 files |
| Phase 02 P03 | 4 | 2 tasks | 3 files |
| Phase 02 P05 | 8 | 2 tasks | 3 files |
| Phase 02 P06 | 52 | 2 tasks | 2 files |
| Phase 03 P01 | 4 | 2 tasks | 4 files |
| Phase 03 P03 | 4 | 2 tasks | 3 files |
| Phase 03 P02 | 5 | 2 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Modularize into separate Python modules: 2,300-line monolith is hard to test and maintain
- exec() replacement must be the first commit before any module extraction
- Full gene mapping rework over incremental fix: HGNC static download + wrong predicates need holistic solution
- Predicate changes are breaking — SNORQL audit required before Phase 3 ships
- Separate pure vs enriched RDF: provenance clarity; file-level separation is sufficient (named graphs deferred)
- RDF output validation only (not source XML): focus on what we control and ship
- [Phase 01]: Transitional exec in pipeline.py: main(config) API is clean but internally execs monolith. Removed in Phase 2.
- [Phase 01]: Header skipped unconditionally to handle both old Synonyms and new Alias symbols HGNC formats
- [Phase 01]: download_hgnc_data takes individual parameters not PipelineConfig for decoupling
- [Phase 01]: Config optional for parse_aopwiki_xml: when None, network calls skipped for offline testing
- [Phase 01]: celldict/organdict populated from KE cell-term/organ-term for standalone access
- [Phase 02]: Generic batch_xrefs pattern factored from gene/chemical BridgeDb implementations with parse_fn + fallback_fn injection
- [Phase 02]: Protein ontology return keys prefixed pro_ (pro_hgnclist) to prevent confusion with gene-mapping hgnclist
- [Phase 02]: GENES_PREFIXES and VOID_PREFIXES stored as exact string constants for byte-identical RDF output
- [Phase 02]: BridgeDb batch logic inlined in gene_mapper rather than importing from bridgedb.py (parallel wave)
- [Phase 02]: False positive filter constants promoted to module-level for testability
- [Phase 02]: Lazy import in parser for chemical_mapper to avoid circular dependency between parser and mapping packages
- [Phase 02]: Chemical mapper reads CAS from chedict property rather than re-parsing XML
- [Phase 02]: Orchestrator parses XML separately to provide xml_root to mapping stages (ParsedEntities lacks root/ns fields)
- [Phase 02]: Chemical identifier lists reconstructed from chedict since ParsedEntities does not expose them
- [Phase 02]: parse_aopwiki_xml called with config=None to skip internal promapping, deferring to protein_ontology module
- [Phase 02]: Regression test normalizes file:// URIs, blank nodes, ISO dates, and ctime dates before NTriples comparison
- [Phase 02]: Redundant local import time in monolith removed to fix UnboundLocalError scoping bug
- [Phase 03]: Keep BridgeDb system code H (symbol) with symbol_lookup reverse mapping instead of switching to Hac
- [Phase 03]: Gene dicts re-keyed from symbol to numeric HGNC ID with symbol_lookup flowing through pipeline context
- [Phase 03]: No hgnc:SYMBOL patterns found in SPARQL queries -- no additional gene URI migration needed
- [Phase 03]: GitHub issue approach for tracking external aopwiki-snorql-extended repo updates
- [Phase 03]: config=None defaults to owl:sameAs only for safe backward compatibility
- [Phase 03]: rdfs:label on gene nodes uses symbol_lookup with fallback to numeric ID

### Pending Todos

None yet.

### Blockers/Concerns

- [RESOLVED] The `aopwiki-snorql-extended` SPARQL query inventory has been audited; GitHub issue #70 tracks external repo updates
- [Pre-Phase 5] Property population audit (SPARQL query against current TTL) must run before any SHACL shape is written

## Session Continuity

Last session: 2026-03-08T09:03:15.045Z
Stopped at: Completed 03-02-PLAN.md
Resume file: None
