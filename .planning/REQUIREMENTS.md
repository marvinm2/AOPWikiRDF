# Requirements: AOPWikiRDF Pipeline Modernization

**Defined:** 2026-03-04
**Core Value:** Produce accurate, well-structured RDF from AOP-Wiki XML every week — reliably and with traceable provenance for pure vs enriched content.

## v1 Requirements

### Modularization

- [x] **MOD-01**: Replace `exec()`/string-replacement config with Python dataclass-based configuration
- [x] **MOD-02**: Extract XML parser into a standalone module with defined input/output contracts
- [x] **MOD-03**: Extract gene mapper into a standalone module with defined input/output contracts
- [x] **MOD-04**: Extract chemical mapper into a standalone module with defined input/output contracts
- [x] **MOD-05**: Extract RDF writer(s) into standalone module(s) with defined input/output contracts
- [x] **MOD-06**: Create thin orchestrator that wires modules together and replaces monolithic execution
- [x] **MOD-07**: Modularized pipeline produces identical RDF output compared to current monolithic script (triple-for-triple regression test)

### Predicate Correction

- [ ] **PRED-01**: Replace `skos:exactMatch` with `owl:sameAs` for all cross-database identifier links (chemicals and genes)
- [ ] **PRED-02**: Fix HGNC namespace usage — use numeric HGNC IDs for identifier URIs, retain symbols as queryable properties (e.g. `rdfs:label` or `skos:prefLabel`)
- [ ] **PRED-03**: Audit downstream SNORQL SPARQL queries for `skos:exactMatch` usage and document required changes
- [ ] **PRED-04**: Ensure HGNC gene symbols remain queryable in the RDF after ID/predicate corrections

### Gene Mapping Rework

- [x] **GENE-01**: Implement dynamic HGNC data download at pipeline startup via BioMart endpoint
- [x] **GENE-02**: Fall back to cached static HGNC file when dynamic download fails
- [ ] **GENE-03**: Maintain existing three-stage precision filtering (screening, precision matching, false positive filtering)
- [ ] **GENE-04**: Gene mapping module is independently testable with unit tests

### BioBERT Exploration

- [ ] **BIO-01**: Build prototype NER pipeline using BioBERT (or similar biomedical model) on a subset of Key Event descriptions
- [ ] **BIO-02**: Compare BioBERT precision and recall against current HGNC regex-based mapping
- [ ] **BIO-03**: Document findings, feasibility assessment, and integration path for future adoption

### Output Separation

- [ ] **SEP-01**: Separate pure AOP-Wiki RDF (source-derived triples only) into its own TTL file
- [ ] **SEP-02**: Separate enriched/associated content (gene mappings, chemical cross-references) into distinct TTL file(s)
- [ ] **SEP-03**: Add `void:subset` declarations linking separated files in VoID metadata

### Validation

- [ ] **VAL-01**: Audit current RDF output to determine which properties are required vs optional per entity type
- [ ] **VAL-02**: Define SHACL shapes for core entity types: AOP, Key Event, KER, Stressor, Chemical
- [ ] **VAL-03**: Integrate SHACL validation as a triggered GitHub Actions workflow (separate from generation)
- [ ] **VAL-04**: SHACL validation completes within GitHub Actions time limits on full RDF output

### Documentation & VoID

- [ ] **DOC-01**: Write schema documentation covering RDF structure, namespaces, and entity types
- [ ] **DOC-02**: Document conversion process and mapping strategy (gene mapping, chemical mapping, precision filtering)
- [ ] **DOC-03**: Enrich VoID metadata with `void:triples`, `dcterms:license`, `pav:importedFrom` for BridgeDb enrichment
- [ ] **DOC-04**: Add `void:exampleResource` entries for discoverability

## v2 Requirements

### YARRML Transition

- **YARRML-01**: Investigate YARRML mapping patterns for AOP-Wiki XML structure
- **YARRML-02**: Design hybrid YARRML + Python post-processing approach
- **YARRML-03**: Update GitHub Actions workflow for YARRML integration

### KER Relationships

- **KER-01**: Extract KER relationship overview data from XML into RDF (#68)

### Advanced NER

- **NER-01**: Full BioBERT integration into production pipeline (pending prototype results from BIO-01/02/03)

## Out of Scope

| Feature | Reason |
|---------|--------|
| YARRML transition (#60-63) | Separate collaboration with Saurav Kumar, different timeline |
| KER overview extraction (#68) | Deferred to future round |
| Real-time conversion | Weekly batch is the deployment model |
| Mobile/web UI | This is a data pipeline, not user-facing |
| rdflib 7.x upgrade | Unresolved risk — may affect serialization behavior; evaluate separately |
| Named graphs for provenance | File-level separation is simpler and sufficient for batch pipeline |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MOD-01 | Phase 1 | Complete |
| MOD-02 | Phase 1 | Complete |
| GENE-01 | Phase 1 | Complete |
| GENE-02 | Phase 1 | Complete |
| MOD-03 | Phase 2 | Complete |
| MOD-04 | Phase 2 | Complete |
| MOD-05 | Phase 2 | Complete |
| MOD-06 | Phase 2 | Complete |
| MOD-07 | Phase 2 | Complete |
| PRED-01 | Phase 3 | Pending |
| PRED-02 | Phase 3 | Pending |
| PRED-03 | Phase 3 | Pending |
| PRED-04 | Phase 3 | Pending |
| GENE-03 | Phase 3 | Pending |
| GENE-04 | Phase 3 | Pending |
| SEP-01 | Phase 4 | Pending |
| SEP-02 | Phase 4 | Pending |
| SEP-03 | Phase 4 | Pending |
| DOC-03 | Phase 4 | Pending |
| DOC-04 | Phase 4 | Pending |
| VAL-01 | Phase 5 | Pending |
| VAL-02 | Phase 5 | Pending |
| VAL-03 | Phase 5 | Pending |
| VAL-04 | Phase 5 | Pending |
| DOC-01 | Phase 5 | Pending |
| DOC-02 | Phase 5 | Pending |
| BIO-01 | Phase 5 | Pending |
| BIO-02 | Phase 5 | Pending |
| BIO-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 29 total
- Mapped to phases: 29
- Unmapped: 0

---
*Requirements defined: 2026-03-04*
*Last updated: 2026-03-04 after roadmap creation*
