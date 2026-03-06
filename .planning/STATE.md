---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 02-03-PLAN.md
last_updated: "2026-03-06T15:05:34Z"
last_activity: 2026-03-06 — Completed 02-03 chemical mapper extraction plan
progress:
  total_phases: 5
  completed_phases: 1
  total_plans: 10
  completed_plans: 7
  percent: 70
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-04)

**Core value:** Produce accurate, well-structured RDF from AOP-Wiki XML every week — reliably and with traceable provenance for pure vs enriched content.
**Current focus:** Phase 2 — Module Extraction

## Current Position

Phase: 2 of 5 (Module Extraction)
Plan: 4 of 6 in current phase
Status: In progress
Last activity: 2026-03-06 — Completed 02-03 chemical mapper extraction plan

Progress: [███████░░░] 70%

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

### Pending Todos

None yet.

### Blockers/Concerns

- [Pre-Phase 3] The `aopwiki-snorql-extended` SPARQL query inventory must be audited manually before Phase 3 ships — silent zero-result queries will result from predicate change without this audit
- [Pre-Phase 5] Property population audit (SPARQL query against current TTL) must run before any SHACL shape is written

## Session Continuity

Last session: 2026-03-06T15:05:34Z
Stopped at: Completed 02-03-PLAN.md
Resume file: None
