# Roadmap: AOPWikiRDF Pipeline Modernization

## Overview

The pipeline starts as a 2,281-line monolith with an exec()-based config antipattern, semantically incorrect predicates, no structural validation, and no formal separation between source-derived and enriched triples. The modernization works through five sequential phases, each unblocking the next: the exec() replacement and module scaffold come first (nothing else is safely testable without them), then the remaining module extractions and regression baseline, then coordinated predicate correction and gene mapper rework (must precede SHACL shapes), then pure/enriched file separation and VoID subset declarations, and finally structural validation, documentation, and BioBERT exploration.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Replace exec() config, extract XML parser, add dynamic HGNC download
- [ ] **Phase 2: Module Extraction** - Extract gene/chemical/RDF writer modules and create thin orchestrator with triple-for-triple regression baseline
- [ ] **Phase 3: Predicate Correction** - Fix skos:exactMatch, HGNC ID/symbol distinction, and SNORQL audit with dual-predicate transition
- [ ] **Phase 4: Output Separation** - Separate pure AOP-Wiki RDF from enriched content and enrich VoID with subset declarations
- [ ] **Phase 5: Validation and Documentation** - SHACL shapes, full VoID enrichment, schema documentation, BioBERT exploration

## Phase Details

### Phase 1: Foundation
**Goal**: The pipeline runs from a typed config dataclass, the XML parser is an isolated testable module, and HGNC gene data is downloaded dynamically at startup
**Depends on**: Nothing (first phase)
**Requirements**: MOD-01, MOD-02, GENE-01, GENE-02
**Success Criteria** (what must be TRUE):
  1. The pipeline can be started by constructing a `PipelineConfig` dataclass — no `exec()` or string-replacement config injection exists anywhere in the codebase
  2. `src/aopwiki_rdf/parser/xml_parser.py` can be imported and called independently with an XML file path, returning typed entity objects, without running the full pipeline
  3. HGNC gene data is fetched from the BioMart HTTP endpoint at pipeline startup; a `len(genedict) < 19000` assertion guards against a failed or empty download
  4. When the BioMart download fails, the pipeline falls back to the cached static `HGNCgenes.txt` and logs a warning
**Plans:** 3 plans

Plans:
- [ ] 01-01-PLAN.md — Package scaffold, PipelineConfig dataclass, rewrite run_conversion.py
- [ ] 01-02-PLAN.md — Extract XML parser into standalone module with tests
- [ ] 01-03-PLAN.md — Dynamic HGNC download with fallback and HGNC TSV parser

### Phase 2: Module Extraction
**Goal**: All pipeline logic lives in isolated modules with defined contracts; a thin orchestrator wires them together; the modularized output is verified triple-for-triple against the current monolithic script
**Depends on**: Phase 1
**Requirements**: MOD-03, MOD-04, MOD-05, MOD-06, MOD-07
**Success Criteria** (what must be TRUE):
  1. `mapping/gene_mapper.py`, `mapping/chemical_mapper.py`, and `rdf/writer_*.py` can each be imported and instantiated without importing or running the other modules
  2. A thin `pipeline.py` orchestrator replaces the monolithic execution path and passes named data objects between stages (no shared global state)
  3. Running the modularized pipeline against the current AOP-Wiki XML produces a triple count within 0% of the monolithic script output (regression test passes)
  4. Unit tests exist for the gene mapper and chemical mapper modules that run without network access (injectable config for testing)
**Plans**: TBD

### Phase 3: Predicate Correction
**Goal**: All cross-database identifier links use semantically correct predicates; HGNC gene symbols remain queryable; downstream SPARQL consumers are audited and a safe transition path exists
**Depends on**: Phase 2
**Requirements**: PRED-01, PRED-02, PRED-03, PRED-04, GENE-03, GENE-04
**Success Criteria** (what must be TRUE):
  1. `owl:sameAs` is used for all cross-database identifier links (chemicals and genes); `skos:exactMatch` no longer appears in the generated RDF for identifier links
  2. Gene triples use numeric HGNC IDs for identifier URIs and retain gene symbols as `rdfs:label` or `skos:prefLabel` — a SPARQL query for a known gene symbol returns the correct gene node
  3. A documented inventory of `skos:exactMatch`-dependent queries in `aopwiki-snorql-extended` exists, with each query marked as updated or confirmed unaffected
  4. The existing three-stage precision filtering (screening, precision matching, false positive filtering) is preserved and unit-tested in the isolated gene mapper module
**Plans**: TBD

### Phase 4: Output Separation
**Goal**: Pure AOP-Wiki source triples and pipeline-enriched triples live in distinct TTL files with VoID subset declarations linking them; downstream consumers can load either or both files
**Depends on**: Phase 3
**Requirements**: SEP-01, SEP-02, SEP-03, DOC-03, DOC-04
**Success Criteria** (what must be TRUE):
  1. `AOPWikiRDF.ttl` contains only triples directly derived from AOP-Wiki XML source data — it has no imports from `mapping/` modules and no gene association or chemical cross-reference triples
  2. A separate enriched TTL file contains all gene associations and chemical cross-references with provenance — loading only this file alongside `AOPWikiRDF.ttl` restores the full joined query capability
  3. The VoID metadata file declares `void:subset` relationships between the pure and enriched files, and includes `void:triples`, `dcterms:license`, and `pav:importedFrom` for the BridgeDb enrichment
  4. `void:exampleResource` entries are present in VoID for each core entity type (AOP, Key Event, KER, Chemical)
**Plans**: TBD

### Phase 5: Validation and Documentation
**Goal**: SHACL shapes validate the RDF structure in a separate GitHub Actions workflow; schema and conversion documentation exists; a BioBERT prototype produces a comparative precision/recall report
**Depends on**: Phase 4
**Requirements**: VAL-01, VAL-02, VAL-03, VAL-04, DOC-01, DOC-02, BIO-01, BIO-02, BIO-03
**Success Criteria** (what must be TRUE):
  1. A property population audit has been run against the current RDF output and identifies which properties are required vs optional per entity type — this audit precedes any SHACL shape definition
  2. SHACL shapes exist for `aopo:AdverseOutcomePathway`, `aopo:KeyEvent`, KER, Stressor, and Chemical entity types and produce a machine-readable `sh:ValidationReport` when run against the full RDF output
  3. SHACL validation runs in a separate triggered GitHub Actions workflow (not inline with RDF generation) and completes within GitHub Actions time limits
  4. Schema documentation describes the RDF structure, namespaces, and entity types; conversion documentation covers the gene mapping algorithm, chemical mapping strategy, and precision filtering
  5. A BioBERT NER prototype has been run on a subset of Key Event descriptions and produced a documented precision/recall comparison against the current HGNC regex-based approach with a written feasibility assessment
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/3 | Planning complete | - |
| 2. Module Extraction | 0/TBD | Not started | - |
| 3. Predicate Correction | 0/TBD | Not started | - |
| 4. Output Separation | 0/TBD | Not started | - |
| 5. Validation and Documentation | 0/TBD | Not started | - |
