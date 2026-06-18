---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: XML Coverage, COMPAT Gate & Production Promotion
status: ready_to_plan
stopped_at: Phase 10 complete (1/1) — ready to discuss Phase 11
last_updated: 2026-06-18T13:29:20.677Z
last_activity: 2026-06-18 -- Phase 10 execution started
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 5
  completed_plans: 5
  percent: 25
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-17)

**Core value:** Produce accurate, well-structured RDF from AOP-Wiki XML every week — reliably and with traceable provenance for pure vs enriched content.
**Current focus:** Phase 11 — compat closing gate

> **Milestone history:** v1.0 (phases 1-5, archived) → v1.1 BERN2 NER enrichment (phases A-C, shipped 2026-05-18, retrospective) → v1.2 (phases 6-8: BERN2-primary + IRI labels). v1.2 was planned as phases 6-10 but re-scoped to what shipped; XML coverage (XML-01/02/03) and the COMPAT closing gate (COMPAT-01) deferred to v1.3. ROADMAP.md now carries the v1.3 milestone (Phases 9–12) alongside the archived v1.0–v1.2 sections. See `v1.2-MILESTONE-AUDIT.md`.

## Current Position

Phase: 11
Plan: Not started
Status: Ready to plan
Last activity: 2026-06-18

## v1.3 Phase Map

| Phase | Goal | Requirements | Depends on |
|-------|------|--------------|------------|
| 9 | XML→RDF coverage audit, fix high-value gaps, coverage ratchet | XML-01/02/03 | — (independent, first) |
| 10 | `--enable-iri-labels` CLI flag wiring (off by default) | LABEL-05 | — (precondition for the flip) |
| 11 | COMPAT full-corpus byte-identity closing gate (date-masked, pinned golden) | COMPAT-01 | Phase 10 |
| 12 | Production flag flip (BERN2-primary + IRI labels), gated on green COMPAT | PROMO-01 | Phases 10, 11 |

**Ordering invariants (from research):**

- COMPAT-01 (Phase 11) MUST be proven green BEFORE the flip (Phase 12).
- XML parser fixes (Phase 9 — intentionally change output) MUST NOT be co-mingled with flag-gated promotions (Phases 10–12 — must not change flag-off output).
- NER-05 (self-hosted BERN2) is **out of scope** for v1.3 — no phase.

## Performance Metrics

**Velocity:**

- Total plans completed (v1.3): 0
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| — | 0 | - | - |
| 09 | 4 | - | - |
| 10 | 1 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting v1.3 work:

- **[v1.2]** `enable_iri_labels` shipped programmatic-only — v1.3 adds the CLI flag (LABEL-05, Phase 10) and flips it in production (PROMO-01, Phase 12).
- **[v1.2]** QC delta-guard baselines on `HEAD~1`, not `production-rdf-backup/` — Phase 9 coverage ratchet extends this same pattern; Phase 11 COMPAT golden likewise must NOT use the stale `production-rdf-backup/`.
- **[v1.3 research]** Writer emits manual f-string Turtle, not `rdflib.serialize()` — COMPAT (Phase 11) needs only date-masking + existing `sorted()`, no blank-node canonicalization.
- **[v1.3 research]** Coverage gaps computed vs instance data, not bare XSD declarations — XSD-only would flood the report with optional/empty elements; baseline the ratchet after fixing high-value gaps.
- **[v1.3 research]** NER-05 dropped — full BERN2 needs ~63.5 GB RAM + GPU; cluster nodes have ~31 GB and no GPU (verified by SSH 2026-06-17). Keep external API + committed cache.

### Pending Todos

- [Phase 9 planning] Confirm AOP-XML XSD per-quarter versioning — if one global XSD, derive the per-snapshot element universe from instance data.
- [Phase 11 planning] Decide `data/compat-golden/` repo footprint — commit TTLs vs SHA-256 manifests (by file size).

### Blockers/Concerns

- [RESOLVED, v1.0] Property population audit ran before SHACL shapes were written (scripts/property_audit.py → generate_shapes.py)
- [Carried to v1.3] Phase 12 flip must pre-flight downstream SPARQL `.rq` + dashboard `methodology_notes.json` against a flags-on Virtuoso load before touching `master/data/` (new predicates can break consumers).

## Session Continuity

Last session: 2026-06-18T12:55:33.374Z
Stopped at: Phase 10 context gathered
Resume file: .planning/phases/10-enable-iri-labels-cli-flag-wiring/10-CONTEXT.md
Next: `/gsd-plan-phase 9` (XML→RDF coverage audit + ratchet)
