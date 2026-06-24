# Requirements — Milestone v1.3: XML Coverage, COMPAT Gate & Production Promotion

> REQ-IDs continue numbering from prior milestones (LABEL-01..04 shipped in v1.2).
> Self-hosted BERN2 (NER-05) was evaluated and **dropped** — see Out of Scope.

## Milestone v1.3 Requirements

### XML Coverage (XML)
- [x] **XML-01**: A maintainer can run a single re-runnable script that reports XML→RDF element coverage as machine-readable JSON — diffing AOP-XML elements/attributes (declared in the XSD and/or observed in instance data) against what the parser actually emits, with per-element occurrence counts and snapshot-over-snapshot deltas.
- [x] **XML-02**: High-value coverage gaps (elements present in actual quarterly-snapshot instance data but absent from the RDF output) are fixed in the parser/writer, ranked by occurrence-count × semantic value.
- [x] **XML-03**: A coverage-ratchet regression test plus per-element triple-count QC guards fail the build when coverage regresses below the post-fix baseline, extending the existing `HEAD~1` delta-guard pattern.

### IRI Labels (LABEL)
- [x] **LABEL-05**: A maintainer can enable IRI labels at the command line via a `--enable-iri-labels` flag on `run_conversion.py`, wired through to `PipelineConfig.enable_iri_labels` (off by default until the production flip), mirroring the existing `--enable-bern2` flag.

### Compatibility (COMPAT)
- [ ] **COMPAT-01**: A milestone-level, full-corpus byte-identity closing gate proves that flag-gated changes reproduce the flag-off output exactly. It compares against a pinned, in-repo flag-off golden (regenerated on a committed XML snapshot — never the stale `production-rdf-backup/`), masks embedded wall-clock dates so it does not false-fail across calendar days, and runs as a manual/milestone `workflow_dispatch` job, not in the weekly per-commit pytest.

### Production Promotion (PROMO)
- [ ] **PROMO-01**: BERN2-primary gene annotations and IRI labels go live in `master/data/` by flipping the flags in both the weekly `rdfgeneration.yml` and the `test-python-conversion.yml` regression workflow (kept mirrored), gated on a green COMPAT-01, with downstream SPARQL `.rq` and dashboard `methodology_notes.json` queries pre-flighted against a flags-on Virtuoso load before the flip commit touches `master/data/`. VoID dataset version bumped and `docs/schema.md` updated for the newly live predicates.

## Future Requirements (deferred)

- **NER-05** — Self-hosted BERN2 to remove the external public-API dependency. Blocked on hardware: full BERN2 needs ~63.5 GB RAM + a CUDA GPU; cluster nodes have ~31 GB and no GPU. Revisit only if a GPU/fat-RAM host is provisioned (hardware question for slaenen) **or** a distilled CPU NER fallback (TinyBERN2/scispaCy) passes gene-set parity against current BERN2-primary output.
- **KER-02** (#68) — KER relationship overview extraction.
- **YARRML-01..03** (#60-63) — declarative YARRML/RML mapping transition (separate collaboration).

## Out of Scope (explicit exclusions)

- **Self-hosted BERN2 in v1.3** — infeasible on current hardware (see Future / NER-05). Keep external API + committed cache.
- **Auto-mapping all XSD-declared elements** — would flood the graph with empty/junk triples; only high-value, instance-present gaps are fixed.
- **Full-corpus byte-identity on every weekly run** — COMPAT is a milestone gate, not a per-run check (28–90 min full-corpus cost).
- **Sampled byte-identity** — defeats the purpose of a closing gate; COMPAT is full-corpus.
- **RDFC-1.0 / blank-node canonicalization for COMPAT** — unnecessary; the writer emits manual f-string Turtle, not `rdflib.serialize()`, so the only non-determinism is embedded dates and iteration order.
- **Removing the regex/cache fallback** — retained regardless of any BERN2 topology change.

## Traceability

*(Filled by roadmap — each requirement maps to exactly one phase.)*

| REQ-ID | Phase | Status |
|--------|-------|--------|
| XML-01 | Phase 9 | complete |
| XML-02 | Phase 9 | complete |
| XML-03 | Phase 9 | complete |
| LABEL-05 | Phase 10 | Complete |
| COMPAT-01 | Phase 11 | pending |
| PROMO-01 | Phase 12 | pending |
