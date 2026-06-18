# Roadmap: AOPWikiRDF Pipeline Modernization

> **GSD milestone labels are independent of git tags.** The `v1.0`–`v1.3` git tags are
> unrelated 2019–2020 script versions; GSD v1.0 carries git tag `v2.0`. Milestone work
> ships on `master`. Full per-milestone detail lives in `.planning/milestones/`.

## Milestones

- ✅ **v1.0 Pipeline Modernization** — Phases 1–5 (shipped 2026-03-09)
- ✅ **v1.1 BERN2 NER Gene Enrichment** — Phases A–C (shipped 2026-05-18, tracked retrospectively)
- ✅ **v1.2 BERN2-Primary Gene Mapping & IRI Labels** — Phases 6–8 (shipped 2026-06-17)
- 📋 **v1.3 XML Coverage, COMPAT Gate & Production Promotion** — Phases 9–12 (planned)

## Phases

<details>
<summary>✅ v1.0 Pipeline Modernization (Phases 1–5) — SHIPPED 2026-03-09</summary>

- [x] Phase 1: Foundation (4/4 plans) — completed 2026-03-05
- [x] Phase 2: Module Extraction (6/6 plans) — completed 2026-03-06
- [x] Phase 3: Predicate Correction (3/3 plans) — completed 2026-03-08
- [x] Phase 4: Output Separation (4/4 plans) — completed 2026-03-09
- [x] Phase 5: Validation and Documentation (4/4 plans) — completed 2026-03-09

Replace exec()/monolith with a modular package; extract gene/chemical/RDF-writer modules and
thin orchestrator with triple-for-triple regression; correct predicates (owl:sameAs) and
numeric HGNC IDs; separate pure/enriched RDF with VoID subset metadata; add SHACL shapes +
CI + docs; BioBERT feasibility (do-not-integrate). See `milestones/v1.0-ROADMAP.md`.

</details>

<details>
<summary>✅ v1.1 BERN2 NER Gene Enrichment (Phases A–C) — SHIPPED 2026-05-18</summary>

- [x] Spike: NER+EL feasibility (BERN2 + PubTator3 vs regex baseline)
- [x] Phase A: `ner_el_mapper.py` mapper module (off by default)
- [x] Phase B: Pipeline integration with provenance
- [x] Phase C: Production enablement (`--enable-bern2` in weekly workflow)
- [x] Hardening: warmed cache + `ner_min_prob=0.70`

BERN2 NER+EL added as an *additive* enrichment layer alongside the regex mapper (hosted API,
warmed cache, confidence threshold). Tracked retrospectively. See `milestones/v1.1-bern2-ROADMAP.md`.

</details>

<details>
<summary>✅ v1.2 BERN2-Primary Gene Mapping & IRI Labels (Phases 6–8) — SHIPPED 2026-06-17</summary>

- [x] Phase 6: BERN2 Hardening + QC Delta-Guard (3/3 plans) — NER-03, NER-04, QC-01
- [x] Phase 7: Promote BERN2 to Primary, union preserved (4/4 plans) — GENE-05/06/07/08, NER-02, PROV-01
- [x] Phase 8: External-IRI Labeling (3/3 plans) — LABEL-01/02/03/04

BERN2 promoted to featured/primary gene mapping (regex retained as provenance-tagged
secondary; canonical predicate keeps the union); PROV-O provenance; cache pre-warm + graceful
degradation; QC gene/triple delta-guard; flag-gated `rdfs:label` on all numeric IRIs.
Re-scoped from planned phases 6–10 — phases 9 (XML) & 10 (COMPAT) deferred to v1.3.
See `milestones/v1.2-ROADMAP.md` and `milestones/v1.2-MILESTONE-AUDIT.md`.

</details>

### 📋 v1.3 XML Coverage, COMPAT Gate & Production Promotion (Phases 9–12)

- [x] **Phase 9: XML→RDF Coverage Audit, Gap Fixes & Coverage Ratchet** — Re-runnable JSON coverage report, fix high-value instance-present gaps, coverage-ratchet test + per-element triple-count QC guards (completed 2026-06-18)
- [x] **Phase 10: `--enable-iri-labels` CLI Flag Wiring** — Mechanical CLI→PipelineConfig plumbing, off by default, mirrors `--enable-bern2`; precondition for the flip (completed 2026-06-18)
- [ ] **Phase 11: COMPAT Closing Gate** — Full-corpus, date-masked byte-identity check on a pinned in-repo flags-off golden, proven green before the flip
- [ ] **Phase 12: Production Flag Flip (BERN2-Primary + IRI Labels)** — Flip flags in both weekly + regression workflows, gated on green COMPAT, downstream queries pre-flighted

> Self-hosted BERN2 (NER-05) was evaluated and **dropped** from v1.3 (infeasible on current
> cluster hardware — see PROJECT.md Out of Scope / REQUIREMENTS.md Future). No phase for it.

## Phase Details

### Phase 9: XML→RDF Coverage Audit, Gap Fixes & Coverage Ratchet
**Goal**: A maintainer can see exactly which AOP-Wiki XML elements the parser drops, the high-value gaps are closed, and the build fails if coverage ever regresses.
**Depends on**: Nothing within v1.3 (fully independent of flags / endpoints / COMPAT — lands first)
**Requirements**: XML-01, XML-02, XML-03
**Success Criteria** (what must be TRUE):
  1. A maintainer can run one re-runnable script that emits machine-readable JSON listing each XML element/attribute, whether the parser emits it, per-element occurrence counts, and snapshot-over-snapshot deltas.
  2. Coverage gaps are computed against actual quarterly-snapshot instance data (not bare XSD declarations), so the report surfaces real dropped content rather than optional/empty elements.
  3. High-value gaps (elements present in instance data but absent from the RDF), ranked by occurrence-count × semantic value, are fixed in the parser/writer and now appear in the output.
  4. A coverage-ratchet regression test plus per-element triple-count QC guards fail the build when coverage drops below the post-fix baseline, extending the existing `HEAD~1` delta-guard pattern.
**Plans**: 4 plans
- [x] 09-01-PLAN.md — Wave 0: vendor pinned XSD + provenance, fix gitignore swallow, allowlist (D-09), Nyquist test stubs + regression fixture
- [x] 09-02-PLAN.md — XML-01: re-runnable coverage_audit.py + committed coverage-report.json (instance vs covered, both axes, graceful historical skip)
- [x] 09-03-PLAN.md — XML-02: maintainer-selected high-value gap fixes in parser/writer (additive), prefix registration
- [x] 09-04-PLAN.md — XML-03: freeze post-fix ratchet baseline (D-11), per-element guard + --warn-only, CI two-posture wiring

### Phase 10: `--enable-iri-labels` CLI Flag Wiring
**Goal**: A maintainer can toggle IRI labels from the command line, with the flag wired through to the pipeline config and off by default — making the production flip a one-line workflow change.
**Depends on**: Nothing within v1.3 (mechanical; can land any time before Phase 12)
**Requirements**: LABEL-05
**Success Criteria** (what must be TRUE):
  1. Running `run_conversion.py --enable-iri-labels` sets `PipelineConfig.enable_iri_labels = True` and produces output carrying the labels.
  2. With the flag absent, `enable_iri_labels` stays `False` and the output is byte-identical to today's flag-off output (the labeling code does not fire).
  3. The flag mirrors the existing `--enable-bern2` flag in argparse surface and help text, and the forbidden-token / CLI guard is extended to cover it.
**Plans**: 1 plan
- [x] 10-01-PLAN.md — LABEL-05: wire --enable-iri-labels into run_conversion.py (flat copy of --enable-bern2), off by default, with build_config testability helper + config-default and CLI argparse->config wiring tests

### Phase 11: COMPAT Closing Gate
**Goal**: A maintainer can prove, byte-for-byte, that the flag-gated v1.2/v1.3 infrastructure reproduces production output exactly when the flags are off — the safety proof that must exist before the flip.
**Depends on**: Phase 10 (the `--enable-iri-labels` flag must exist so the gate can exercise flags-off vs flags-on deterministically)
**Requirements**: COMPAT-01
**Success Criteria** (what must be TRUE):
  1. A full-corpus byte-identity check (`scripts/compat_check.py`) compares a fresh flags-off run against a pinned, in-repo flags-off golden regenerated on a committed XML snapshot — never the stale `production-rdf-backup/`.
  2. The check masks embedded wall-clock dates (`# Generated:` header, `pav:createdOn` in VoID/ServiceDescription) so it does not false-fail across calendar days — verified to pass on two different dates with no data change.
  3. No blank-node canonicalization is implemented: the writer emits manual f-string Turtle (not `rdflib.serialize()`), so the gate relies only on date-masking plus the existing `sorted()` iteration order.
  4. The gate runs as a manual / milestone `workflow_dispatch` job (`compat-gate.yml`), not in the weekly per-commit pytest, and reports a readable per-subject diff on failure.
**Plans**: TBD

### Phase 12: Production Flag Flip (BERN2-Primary + IRI Labels)
**Goal**: BERN2-primary gene annotations and IRI labels go live in `master/data/`, with downstream consumers verified to still work — promoting the v1.2 infrastructure to production output.
**Depends on**: Phase 11 (the flip commits only once COMPAT-01 is green) and Phase 10 (the CLI flag being flipped)
**Requirements**: PROMO-01
**Success Criteria** (what must be TRUE):
  1. The flags are flipped on in BOTH `rdfgeneration.yml` and `test-python-conversion.yml`, kept mirrored, so the weekly run and the regression run emit identical flags-on output.
  2. Before the flip commit touches `master/data/`, the curated downstream SPARQL `.rq` queries and the dashboard `methodology_notes.json` queries are pre-flighted against a flags-on Virtuoso load and confirmed to still resolve.
  3. The live `master/data/*.ttl` carries BERN2-primary annotations + IRI labels, the VoID dataset version is bumped, and `docs/schema.md` documents the newly live predicates.
  4. The flip is additive (counts go up), so the QC delta-guard does not false-alarm; the elevated post-flip baseline is left intact (the guard intentionally becomes more sensitive to BERN2 outages — `--drop-pct` is not loosened).
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 4/4 | Complete | 2026-03-05 |
| 2. Module Extraction | v1.0 | 6/6 | Complete | 2026-03-06 |
| 3. Predicate Correction | v1.0 | 3/3 | Complete | 2026-03-08 |
| 4. Output Separation | v1.0 | 4/4 | Complete | 2026-03-09 |
| 5. Validation and Documentation | v1.0 | 4/4 | Complete | 2026-03-09 |
| A–C. BERN2 NER Enrichment | v1.1 | — | Complete | 2026-05-18 |
| 6. BERN2 Hardening + QC Delta-Guard | v1.2 | 3/3 | Complete | 2026-06-01 |
| 7. Promote BERN2 to Primary | v1.2 | 4/4 | Complete | 2026-06-01 |
| 8. External-IRI Labeling | v1.2 | 3/3 | Complete | 2026-06-01 |
| 9. XML→RDF Coverage Audit & Ratchet | v1.3 | 4/4 | Complete   | 2026-06-18 |
| 10. IRI-Labels CLI Flag Wiring | v1.3 | 1/1 | Complete    | 2026-06-18 |
| 11. COMPAT Closing Gate | v1.3 | 0/? | Not started | - |
| 12. Production Flag Flip | v1.3 | 0/? | Not started | - |
