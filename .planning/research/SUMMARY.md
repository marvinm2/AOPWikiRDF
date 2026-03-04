# Project Research Summary

**Project:** AOPWikiRDF Pipeline Modernization
**Domain:** Biomedical RDF generation pipeline — XML-to-RDF ETL with semantic enrichment
**Researched:** 2026-03-04
**Confidence:** HIGH (architecture and pitfalls), MEDIUM (stack additions, features)

## Executive Summary

AOPWikiRDF is a weekly-run ETL pipeline that converts AOP-Wiki XML exports into Linked Data in Turtle format. The existing pipeline works in production and has an active gene mapping precision system (14.6% false positive reduction deployed). The modernization milestone targets four interrelated problems: a 2,281-line monolithic script with an `exec()`-based config injection antipattern, semantically incorrect use of `skos:exactMatch` for cross-database identifier links, the absence of structural (SHACL) RDF validation, and the lack of a formal separation between source-derived and pipeline-enriched triples.

The recommended approach is a four-phase sequential refactor. The dependency order is strict: the `exec()` antipattern and module structure must be resolved first (it creates the testable units on which everything else depends), then the predicate corrections (which must precede SHACL shapes, since shapes validate against predicates), then the pure/enriched file separation, and finally structural validation and VoID enrichment. Attempting any other order creates either untestable code or shapes that validate against incorrect predicates. The architecture research is grounded in direct code analysis at specific line numbers and carries HIGH confidence.

The primary risk is silent regression during the monolith split: the current pipeline relies on shared mutable global state across pipeline stages, and naive modularization will silently drop gene annotations without any syntax error or test failure. This is mitigated by defining explicit data contracts before moving any code, running end-to-end triple-count regression tests after each module extraction, and replacing `exec()` as the very first commit of the refactor. A secondary risk is the `skos:exactMatch` predicate change breaking downstream SPARQL consumers; this requires auditing the `aopwiki-snorql-extended` interface and running dual-predicate output during a transition period.

---

## Key Findings

### Recommended Stack

The existing stack (rdflib 6.3.2, requests, pandas, SPARQLWrapper) is not re-evaluated. Four additions are recommended for the modernization milestone.

**Core technology additions:**

- **`pyshacl` (>=0.25.0):** SHACL shape validation — recommended over ShEx because it integrates natively with rdflib Graph objects, SHACL is a W3C Recommendation (2017), and the AOP-Wiki RDF uses OWL/ontology-aligned namespaces where SHACL is the dominant choice. ShEx would add toolchain complexity with no benefit for this use case.
- **`pytest` (>=7.0):** Testing framework — already implied by the `tests/` directory structure; the modular refactor makes proper unit tests possible for the first time.
- **`dataclasses` (stdlib):** Configuration management — replace the `exec()`/string-replacement config injection with a typed `PipelineConfig` dataclass. No new dependency; available in Python 3.7+.
- **`owl:sameAs` predicate (already in rdflib):** Replace three occurrences of `skos:exactMatch` for URI-to-URI cross-database identifier links. No new library; rdflib already has `OWL.sameAs`.

One pending verification: rdflib 7.x was in development as of mid-2025. Check whether upgrading from 6.3.2 to 7.x is beneficial before the modularization work begins, since a major version change alongside a refactor creates compounded risk.

HGNC gene data should be downloaded dynamically at pipeline startup via the HGNC BioMart HTTP endpoint rather than read from the static `HGNCgenes.txt` committed to the repo. The existing `requests` library handles this; no new dependency is needed.

### Expected Features

The feature research distinguishes table stakes (expected by any RDF dataset consumer) from differentiators and explicitly defers out-of-scope work.

**Must have (table stakes):**
- **Correct ID mapping predicates** — `skos:exactMatch` is semantically wrong for cross-database identifier links; breaks federated queries and OWL reasoning; affects every downstream consumer. This is broken and must be fixed before anything else.
- **Separated pure vs enriched RDF** — consumers must be able to trust that `AOPWikiRDF.ttl` reflects only source-asserted AOP-Wiki content; enriched gene/chemical annotations must carry distinct provenance.
- **`dcterms:license` in VoID** — currently absent; blocks Bio2RDF and EBI registry submission. A one-line fix.
- **Documented RDF schema** — no class/property dictionary exists; any published dataset requires one.

**Should have (differentiators):**
- **SHACL shape validation** — structural QA beyond syntax; 5-10 shapes covering `aopo:AdverseOutcomePathway`, `aopo:KeyEvent`, chemical entities, and gene nodes. Produces machine-readable `sh:ValidationReport`.
- **VoID enrichment** — add `void:triples`, `void:sparqlEndpoint`, `void:exampleResource`, `pav:importedFrom` (for BridgeDb provenance). Low effort, high value for FAIR compliance.
- **Dynamic HGNC download** — prevents gene mapping false negatives from stale symbols; feeds into the gene mapper module redesign.
- **Mapping success/failure reporting in VoID** — publish gene and chemical mapping statistics per-run (counts of successes, failures, reasons).

**Defer (v2+ / separate milestone):**
- YARRML migration — tracked in issues #60-63, active collaboration with Saurav Kumar; separate timeline.
- Named graph per-triple provenance — file-level provenance is sufficient; named graphs would degrade Virtuoso performance.
- BioBERT NER for gene mapping — speculative precision gain; current three-stage regex pipeline is validated.
- SPARQL statistical reports on every commit — 5-10 minute runtime overhead; keep `AOP-Wiki_stats.ipynb` for manual use.
- Real-time or event-driven conversion — weekly batch is the correct model given AOP-Wiki update cadence.

### Architecture Approach

The recommended architecture transforms the 2,281-line monolith into a `src/aopwiki_rdf/` Python package with explicitly bounded modules, a typed `PipelineConfig` dataclass replacing the `exec()`-based injection, and a linear pipeline orchestrator with named data handoffs between stages. The critical architectural boundary is between `rdf/writer_aop.py` (pure source-derived triples) and `rdf/writer_enriched.py` (gene and chemical enrichment triples) — this boundary must be enforced at the import level, not merely by convention.

**Major components:**
1. **`config.py`** — Typed `PipelineConfig` dataclass; the entry point builds it from CLI args; all modules receive it as a parameter. Eliminates `exec()`.
2. **`parser/` (xml_parser.py + models.py)** — ElementTree XML parsing producing typed entity dataclasses (`KeyEvent`, `AOP`, `KER`, `Chemical`); replaces bare nested dicts.
3. **`mapping/` (chemical_mapper.py + gene_mapper.py)** — Isolated BridgeDb batch API calls and HGNC three-stage text-mining; injectable via config for testing without network.
4. **`rdf/` (writer_aop.py + writer_enriched.py + writer_core.py)** — Separated pure and enriched triple writers; `writer_aop.py` must not import from `mapping/`.
5. **`validation/` (rdf_validator.py + xml_validator.py)** — pyshacl integration and rdflib Turtle syntax check; writes `qc-status.txt`.
6. **`void_generator.py`** — VoID metadata generation consuming entity counts from parser output.
7. **`pipeline.py`** — Thin orchestrator with explicit named data handoffs between stages; no global state.

Build order from ARCHITECTURE.md: config and models first (all other modules depend on them), then fetcher/parser, then mapping, then RDF writers, then VoID and validation, then the pipeline orchestrator and entry point.

### Critical Pitfalls

Five critical pitfalls were identified, all grounded in specific code line references.

1. **Silent state contract breakage during module extraction** — The monolith uses shared mutable global dicts across pipeline stages. Modularizing without explicit data contracts will silently drop gene annotations with no error. Mitigate by defining input/output contracts before moving any code and running triple-count regression tests after each extraction.

2. **`skos:exactMatch` predicate change breaks downstream SPARQL consumers** — The `aopwiki-snorql-extended` interface queries `skos:exactMatch` for gene and chemical cross-references. Changing the predicate without auditing downstream queries produces silent zero-result queries. Mitigate by auditing all SPARQL queries in the repo and the SNORQL interface, running dual-predicate output during transition, and adding a SPARQL regression test.

3. **HGNC static file drift causes silent false negatives in gene mapping** — The committed `HGNCgenes.txt` is not refreshed weekly. Renamed gene symbols (e.g., the SEPTIN family) produce no match rather than a wrong match, invisible to precision metrics. Mitigate by downloading HGNC at pipeline startup and adding a `len(genedict1) < 19000` assertion after loading.

4. **Pure/enriched file split breaks cross-file SPARQL joins for single-file consumers** — Queries joining `aopo:AdverseOutcomePathway` with gene annotations will return zero results if only one file is loaded. Mitigate by declaring `void:subset` relationships between files in VoID metadata and providing a multi-file Virtuoso load script.

5. **`exec()`-inherited namespace leak makes refactoring brittle** — `run_conversion.py` injects all pipeline variables into `globals()` via `exec()`. Any test or script that imports `run_conversion` will change behavior after the refactor. Mitigate by replacing `exec()` as the very first commit of the modularization phase, not in a later step.

---

## Implications for Roadmap

Based on combined research, a four-phase structure is strongly indicated by the dependency graph in FEATURES.md and the build order in ARCHITECTURE.md.

### Phase 1: Foundation — Config, Models, and Module Structure

**Rationale:** Everything else depends on this phase. The `exec()`/string-replacement antipattern must be eliminated first because it prevents stable imports, which prevents unit tests, which prevents safe refactoring of any other component. This phase has no external service dependencies and no RDF output changes — the lowest risk entry point.

**Delivers:**
- `src/aopwiki_rdf/` package skeleton
- `PipelineConfig` dataclass replacing `exec()`-based config injection
- Typed entity dataclasses (`AOP`, `KeyEvent`, `KER`, `Chemical`) replacing bare nested dicts
- `fetcher/downloader.py` and `parser/xml_parser.py` as isolated, testable modules
- Dynamic HGNC download integrated into the fetcher
- XML schema validation at parser boundary (guards against silent AOP-Wiki schema changes)

**Addresses (from FEATURES.md):** Dynamic HGNC download; modular testable code.

**Avoids (from PITFALLS.md):** Pitfall 5 (exec namespace leak); Pitfall 3 (HGNC staleness); Pitfall 8 (XML schema changes).

**Research flag:** Standard Python packaging patterns — no additional research needed. Build order from ARCHITECTURE.md is complete.

---

### Phase 2: Predicate Correction and Gene Mapping Rework

**Rationale:** This phase must follow Phase 1 (the gene mapper is now an isolated module) and must precede Phase 3 (SHACL shapes must be defined against correct predicates, not `skos:exactMatch`). The predicate change and gene mapping rework are a single coordinated change per PITFALLS.md — they must not be sequential.

**Delivers:**
- `mapping/gene_mapper.py` and `mapping/chemical_mapper.py` as isolated modules with unit tests
- `skos:exactMatch` replaced by `owl:sameAs` across all three usage sites (biological objects line 1584, chemical identifiers line 1654, gene identifiers line 2165)
- HGNC symbol/ID distinction fixed (HGNC symbols vs HGNC numeric IDs are different; genes file must use correct IDs)
- Species context check in gene mapper (document Human-only mapping limitation)
- BridgeDb system code map extended with warning logging for unknown codes
- Downstream SPARQL query audit completed; dual-predicate transition output during handoff

**Addresses (from FEATURES.md):** Correct ID mapping predicates (table stakes, currently broken).

**Avoids (from PITFALLS.md):** Pitfall 2 (downstream SPARQL breakage); Pitfall 9 (species ambiguity); Pitfall 11 (BridgeDb system code map).

**Research flag:** The downstream SNORQL interface (`aopwiki-snorql-extended`) must be audited manually before this phase ships. This is a coordination step, not additional research.

---

### Phase 3: Pure/Enriched Separation and RDF Writers

**Rationale:** This phase follows Phase 2 because the pure/enriched boundary requires correct predicates to be meaningful. The `rdf/writer_aop.py` module cannot enforce the pure/enriched boundary until the mapping modules are isolated (Phase 1) and produce correctly-predicated output (Phase 2).

**Delivers:**
- `rdf/writer_aop.py` — pure source-derived AOP triples only (no imports from `mapping/`)
- `rdf/writer_enriched.py` — gene associations and chemical cross-references with provenance
- `rdf/writer_core.py` — shared Turtle serialization helpers using rdflib `Literal()` for escaping (eliminates Pitfall 13)
- Non-atomic output write replaced with temp-file-and-rename pattern (Pitfall 10)
- `void:subset` relationships declared in VoID to document multi-file dependency
- SHACL namespace declarations moved out of main `AOPWikiRDF.ttl` into a separate file (Pitfall 12)

**Addresses (from FEATURES.md):** Separated pure vs enriched RDF (table stakes, currently not done).

**Avoids (from PITFALLS.md):** Pitfall 1 (state contract breakage — data contracts defined in Phase 1 enforced here); Pitfall 4 (cross-file join breakage); Pitfall 10 (non-atomic output); Pitfall 12 (SHACL prefix pollution); Pitfall 13 (string concatenation escaping).

**Research flag:** Standard RDF writer patterns — no additional research needed. The architecture provides complete module boundaries.

---

### Phase 4: Validation, VoID Enrichment, and Documentation

**Rationale:** This phase completes the pipeline. SHACL shapes can only be written correctly against the predicates established in Phase 2 and the file structure established in Phase 3. VoID enrichment (triple counts, mapping statistics) depends on modular output from Phases 1-3. Documentation stabilizes only after predicates are fixed.

**Delivers:**
- `validation/rdf_validator.py` with pyshacl integration (5-10 SHACL shapes for core entity types)
- SHACL validation in a separate triggered workflow (not inline with RDF generation — Pitfall 7)
- `void:triples`, `void:sparqlEndpoint`, `void:exampleResource`, `pav:importedFrom` for BridgeDb added to VoID
- `dcterms:license` added to VoID (blocks Bio2RDF/EBI registry without it)
- Mapping success/failure statistics reported in VoID
- Schema documentation: property/class dictionary for each entity type
- `pipeline.py` orchestrator integrating all modules with clean entry point

**Addresses (from FEATURES.md):** SHACL shape validation; VoID enrichment; schema documentation; `dcterms:license`.

**Avoids (from PITFALLS.md):** Pitfall 6 (over-constraining optional fields — requires property population audit first); Pitfall 7 (workflow timeout — SHACL runs in separate workflow).

**Research flag:** The property population audit for SHACL shapes requires running SPARQL queries against the current output before writing any shape definition. This is an implementation-time step, not additional upfront research. Run `SELECT ?prop (COUNT(?s) AS ?n) WHERE { ?s ?prop ?o } GROUP BY ?prop ORDER BY DESC(?n)` against the current TTL before defining shapes.

---

### Phase Ordering Rationale

The four-phase order is driven by three hard dependency chains from FEATURES.md:

1. **Modular code is a precondition for everything** — unit tests, predicate fixes, pure/enriched separation, and SHACL shapes are all easier and safer in isolated modules. The monolith makes any change high-risk.
2. **Correct predicates must precede SHACL shapes** — shapes are defined against specific property IRIs; shapes written against `skos:exactMatch` would be immediately invalidated by Phase 2.
3. **Pure/enriched separation must precede full VoID enrichment** — per-file provenance metadata (pav:importedFrom, void:subset) only makes sense once the files have distinct identities.

The exec() replacement and HGNC dynamic download are placed in Phase 1 (not separate phases) because they are required foundations with no external dependencies and low risk when done first.

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 2** — The downstream SPARQL query audit across `aopwiki-snorql-extended` is required before the phase can be considered complete. This is a coordination dependency, not a research gap. The transition strategy (dual-predicate output during cutover) is clear from PITFALLS.md.

**Phases with standard patterns (skip research-phase):**
- **Phase 1** — Python packaging, dataclasses, dynamic HTTP download: all standard patterns with complete implementation guidance in ARCHITECTURE.md and STACK.md.
- **Phase 3** — RDF writer module separation: architecture is fully specified in ARCHITECTURE.md with explicit import-level enforcement rules.
- **Phase 4** — pyshacl integration: complete implementation pattern in STACK.md; workflow separation strategy in PITFALLS.md.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | SHACL/pyshacl recommendation is HIGH confidence (W3C standard + direct rdflib integration confirmed); HGNC BioMart URL format is MEDIUM (stable as of Aug 2025, verify parameters before implementing); rdflib 7.x upgrade question unresolved |
| Features | MEDIUM-HIGH | Table stakes derived from W3C standards (SHACL, VoID, DCAT, SKOS) — HIGH; WikiPathways/DisGeNET/UniProt predicate patterns from training knowledge (Aug 2025) — MEDIUM, should be verified against current dataset documentation |
| Architecture | HIGH | All findings grounded in direct line-number code analysis of the production script; build order derived from actual import dependencies |
| Pitfalls | HIGH | All 13 pitfalls reference specific line numbers in the codebase or documented concerns in `.planning/codebase/CONCERNS.md`; no training-knowledge-only claims |

**Overall confidence:** HIGH for implementation approach, MEDIUM for external ecosystem claims (predicate conventions in other biomedical RDF datasets)

### Gaps to Address

- **rdflib version:** Current codebase uses 6.3.2; rdflib 7.x was in development as of Aug 2025. Verify whether upgrading alongside the modularization is beneficial or risky. Check PyPI before Phase 1 begins.
- **pyshacl version:** Verify current stable version with `pip index versions pyshacl`. STACK.md recommends >=0.25.0 but this was mid-2025 data.
- **WikiPathways/DisGeNET/UniProt predicate conventions:** The FEATURES.md analysis of how comparable datasets handle ID mapping predicates is based on training knowledge. Verify against current published documentation before finalizing Phase 2 predicate choices.
- **HGNC BioMart download URL:** Verify the exact column parameter names (`gd_hgnc_id`, `gd_app_sym`, etc.) against current genenames.org documentation before implementing the dynamic download.
- **`aopwiki-snorql-extended` SPARQL query inventory:** Not analyzed during research. Must be audited manually before Phase 2 ships to prevent silent breakage in the downstream consumer.

---

## Sources

### Primary (HIGH confidence)

- Direct code analysis: `AOP-Wiki_XML_to_RDF_conversion.py` (2,281 lines, 2026-03-04)
- Direct code analysis: `run_conversion.py` (69 lines, 2026-03-04)
- `.planning/codebase/CONCERNS.md` — documented concerns audit
- `.planning/codebase/ARCHITECTURE.md` — prior layer and data flow analysis
- `.planning/PROJECT.md` — active requirements and constraints
- `data/AOPWikiRDF.ttl`, `data/AOPWikiRDF-Genes.ttl`, `data/AOPWikiRDF-Void.ttl` — direct inspection
- W3C SHACL Recommendation (https://www.w3.org/TR/shacl/) — stable standard, 2017
- W3C SKOS Reference (https://www.w3.org/TR/skos-reference/) — stable standard, 2009; `skos:exactMatch` semantics
- W3C OWL 2 Reference — `owl:sameAs` semantics for entity identity
- Python stdlib `dataclasses` documentation — standard library, stable since Python 3.7

### Secondary (MEDIUM confidence)

- HGNC BioMart download URL format — training knowledge (Aug 2025); verify parameters before implementation
- pyshacl library version and maintenance status — training knowledge (Aug 2025); verify on PyPI
- WikiPathways RDF predicate conventions — training knowledge (Aug 2025); verify against current documentation
- DisGeNET RDF predicate conventions — training knowledge (Aug 2025); verify against current documentation
- UniProt RDF predicate conventions — training knowledge (Aug 2025); verify against current documentation

### Tertiary (LOW confidence)

- rdflib 7.x availability and upgrade path — referenced as "in development as of 2025"; verify current status before Phase 1

---

*Research completed: 2026-03-04*
*Ready for roadmap: yes*
