# Feature Landscape

**Domain:** Biomedical RDF pipeline — XML-to-RDF ETL with semantic enrichment
**Researched:** 2026-03-04
**Confidence:** MEDIUM-HIGH (based on codebase audit + training knowledge of semantic web standards; WebSearch/WebFetch unavailable)

---

## Context: What This Pipeline Actually Does

AOPWikiRDF converts AOP-Wiki XML exports into Linked Data in Turtle format. It has three output files:
- `AOPWikiRDF.ttl` — source-derived AOP triples (AOPs, KEs, KERs, chemicals, biological objects)
- `AOPWikiRDF-Genes.ttl` — enriched gene mappings mined from KE text
- `AOPWikiRDF-Void.ttl` — dataset metadata

Downstream consumers include SPARQL endpoints, the aopwiki-snorql-extended interface, and semantic web researchers. The milestone being planned addresses: correct predicates for ID mappings, pure/enriched separation, shape validation, module structure, and documentation.

---

## Table Stakes

Features users of biomedical RDF datasets expect. Missing = dataset feels unusable or untrustworthy.

| Feature | Why Expected | Complexity | Current Status |
|---------|--------------|------------|----------------|
| Correct ID mapping predicates | `skos:exactMatch` conflates gene symbols ↔ protein/gene URIs (a concept relation) with identity relations between identifiers. Community standard: use `owl:sameAs` for identity, `skos:exactMatch` for closely-matched concepts, `dcterms:identifier` or `cheminf:` properties for literal identifier values. Misuse breaks federated queries and OWL reasoning. | Medium | **Broken** — current code uses `skos:exactMatch` for both protein biological objects (where it is approximately correct) and gene ID mappings in the genes file (where `edam:data_1025` to HGNC identifier URIs is used, which is also non-standard for identity). ChEMBL, WikiPathways, and UniProt RDF use `skos:exactMatch` only for concept equivalence, not for literal identifier strings. |
| Syntactically valid Turtle output | RDF must parse cleanly in all standard parsers (rdflib, Jena, Virtuoso). | Low | Done — rdflib QC workflow validates this weekly |
| VoID dataset description | Semantic web standard for dataset discoverability (void:Dataset, triple count, subject URIs, example resources, sparqlEndpoint). Required by data catalogues. | Low | Partial — VoID exists but is sparse. Missing: `void:triples`, `void:distinctSubjects`, `void:properties`, `void:exampleResource`, `void:sparqlEndpoint`. |
| DCAT metadata | DCAT 2 is the W3C standard for data catalogue interoperability. Required for EBI, Bio2RDF, Linked Open Data Cloud registration. | Low | Partial — `dcat:downloadURL` and some dcterms used, but no `dcat:Dataset` class, `dcat:distribution`, or `dcat:keyword`. |
| Stable, resolvable URIs | External identifiers must resolve to something useful. At 73%, ~27% of URIs fail to resolve. Affects linked data traversal. | High | Monitored but unresolved — needs per-prefix investigation and remediation |
| Separated pure vs enriched data | Users need to know which triples come directly from AOP-Wiki source vs. which are pipeline-derived enrichments (gene NLP mining, BridgeDb cross-references). Provenance-mixing degrades reusability and trustworthiness. | Medium | **Not done** — all triples from enrichment share the same file as source-derived triples (except genes, which are separate) |
| RDF syntax validation in CI | Every commit touching RDF data must be checked for parse errors before merging. | Low | Done |
| Documented RDF schema | Users cannot query data they don't understand. A property/class dictionary is expected for any published dataset. | Medium | **Missing** — no schema documentation exists |

---

## Differentiators

Features not universally expected, but valuable for this specific domain and user base.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Shape-based RDF validation (SHACL or ShEx) | Validates structural constraints beyond syntax: required properties, cardinality, datatype correctness, relationship integrity. SHACL is W3C standard (2017) and widely supported in Python via `pyshacl`. ShEx is used by WikiPathways and Wikidata. Both catch problems rdflib parse validation misses. | Medium | Not implemented. `pyshacl` library available for Python. SHACL recommended over ShEx for this use case (better Python tooling, W3C standard, more expressive for property-level constraints). |
| Per-entity provenance triples | Record *how* each enrichment triple was derived: which source version, which mapping tool version, what date. Enables downstream users to selectively trust or exclude enriched triples. Standard approach: use named graphs or `prov:wasGeneratedBy` / `prov:wasDerivedFrom` per-file or per-triple-cluster. | Medium-High | Currently VoID tracks file-level provenance (`pav:createdWith`, `pav:createdOn`) but not triple-level. Named graphs would require Virtuoso quad store support, which the endpoint has. |
| Mapping success/failure reporting in VoID | Report how many chemicals/genes were mapped successfully, how many failed, and why. Currently silent on partial failures. DisGeNET and similar datasets publish mapping statistics in VoID. | Low | Not implemented but straightforward to add to VoID generation. |
| Dynamic HGNC download | HGNC gene data is currently a static file bundled in the repo. It drifts. Downloading fresh HGNC data each run ensures gene symbols and IDs are current. | Low | Not implemented — tracked as an active requirement in PROJECT.md |
| SPARQL example queries | Published alongside data. Reduces time-to-first-result for new users. WikiPathways, DisGeNET, and Wikidata all provide example query collections. | Low | Partial — `/SPARQLQueries/` directory exists but content not integrated into documentation |
| Modular, testable conversion code | Enables unit-testing individual pipeline stages (XML parser, gene mapper, RDF writer) in isolation. Reduces regression risk during future changes. | High | Not implemented — tracked as active requirement. Key blocker: 2,300-line monolith |
| Triple count badges / dataset statistics in README | Shows dataset is actively maintained and has meaningful content. Standard in Linked Data projects. | Low | Not implemented |
| Zenodo persistent archival | Each weekly run produces a citable, DOI-backed version. Required for academic citation and FAIR compliance. The upload-to-zenodo.yml workflow exists but status is unclear. | Low | Workflow exists; may need activation and testing |

---

## Anti-Features

Features to deliberately NOT build for this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Named graph per-triple provenance | Per-triple provenance via named graphs explodes file size and query complexity. The 16MB main file would grow significantly. Virtuoso performance degrades. | Provenance at file/dataset level (VoID + pav) is sufficient. Per-entity provenance only for gene mappings where it matters most. |
| Custom ontology definitions | AOP-Wiki already has `aopo:`. Adding new ontology classes for pipeline-specific concepts creates maintenance burden and blocks interoperability. | Reuse existing predicates: `prov:`, `pav:`, `dcterms:`, `skos:`, `owl:`. |
| Real-time / event-driven conversion | The pipeline requires AOP-Wiki XML downloads (quarterly updates), BridgeDb API calls, and multi-minute processing. Weekly batch is the correct model for this workload. | Keep weekly GitHub Actions schedule. Document the lag explicitly in VoID `dcterms:accrualPeriodicity`. |
| Mobile / web UI | This is a data pipeline, not an application. Downstream SNORQL interface already serves that purpose. | Out of scope — confirmed in PROJECT.md |
| YARRML migration in this milestone | Separate collaboration with Saurav Kumar. Different timeline and scope. Trying to include it here would block everything else. | Track in issues #60-63, pursue separately |
| Statistical analysis reports (auto-generated) | Running SPARQL stats on every commit adds 5-10 minutes per run and creates large report files that bloat the repo. | Keep AOP-Wiki_stats.ipynb for manual use when needed |
| Full BioBERT NER for gene mapping | ML model integration requires significant infrastructure, adds a GPU/CPU dependency, and the precision gain over the current regex approach is speculative for this domain. | Keep current three-stage regex pipeline, optionally add BioBERT as a separate research spike later |
| Duplicate identifier triples | Current chemical RDF has duplicate URIs in `skos:exactMatch` lists (e.g., `chebi:28201, chebi:28201`). Deduplication is a bug fix, not a feature — but don't add deduplication logic as a general-purpose subsystem. | Fix at the source in the chemical mapping loop; don't build a separate deduplication module |

---

## Feature Dependencies

```
Dynamic HGNC download
  → required before gene mapping rework is complete

Modular code (xml_parser, gene_mapper, rdf_writer)
  → required before meaningful unit test coverage

Correct ID mapping predicates
  → required before shape validation (shapes validate against correct predicates)
  → required before separated pure/enriched RDF (the boundary needs correct semantics)

Separated pure vs enriched RDF
  → requires correct predicates (above)
  → requires modular code (cleaner to implement per-module than in monolith)
  → enables per-file provenance tracking

SHACL shape validation
  → requires correct predicates (shapes defined against correct property IRIs)
  → enables per-run conformance reports

VoID enrichment (triple counts, mapping stats)
  → requires modular code (stats come from separate module outputs)

Schema documentation
  → depends on correct predicates being stabilized first
  → blocks nothing, can be done independently
```

---

## Domain-Specific Findings: The Four Questions

### (1) How do WikiPathways, DisGeNET, UniProt handle ID mapping predicates?

**Confidence: MEDIUM** (training knowledge; WebSearch unavailable for direct verification)

**WikiPathways RDF** uses:
- `wp:bdbHgnc`, `wp:bdbEntrezGene`, `wp:bdbUniprot` — typed predicates per database, not a generic `skos:exactMatch`
- `dcterms:identifier` for the literal identifier string value
- `owl:sameAs` reserved for cases where two URIs denote the same resource (e.g., the same gene in two namespaces)

**UniProt RDF** uses:
- `rdfs:seeAlso` to link from a UniProt entry to external database records
- `up:database` to specify which database the cross-reference belongs to
- Does NOT use `skos:exactMatch` for cross-database identifier links

**DisGeNET RDF** uses:
- `sio:SIO_010078` (gene) → `dcterms:identifier` for HGNC ID as literal
- `owl:equivalentClass` for ontology-level equivalences

**The current AOPWikiRDF pattern** (`skos:exactMatch hgnc:7455, uniprot:P03886`) is problematic because:
- `skos:exactMatch` is a transitive predicate: if `A skos:exactMatch B` and `B skos:exactMatch C`, then `A skos:exactMatch C`. Mixing gene symbols, protein IDs, and UniProt accessions creates unintended transitive closures.
- The correct approach for this pipeline: use `dcterms:identifier` for literal values, `rdfs:seeAlso` or database-specific predicates for URI cross-references, and `owl:sameAs` only for true same-resource identity.
- For gene-to-identifier in the Genes file, `edam:data_1025` (gene identifier) to `hgnc:SYMBOL` is non-standard — the object should be the HGNC numeric ID (e.g., `hgnc:3467`), not the symbol (e.g., `hgnc:FMN1`). HGNC symbols and HGNC IDs are different things.

### (2) What is expected in RDF validation pipelines?

**Confidence: HIGH** (well-established community practice)

Two tiers are standard:

**Tier 1 — Syntactic validation (already done):**
- `rdflib.Graph().parse()` to catch malformed Turtle
- Output: pass/fail + triple count

**Tier 2 — Structural/semantic validation (not done, needed):**
- SHACL (W3C Recommendation, 2017) — defines shapes as RDF graphs, validated with `pyshacl` in Python
- ShEx — alternative used by Wikidata and WikiPathways
- What shapes to define for this pipeline:
  - Every `aopo:AdverseOutcomePathway` must have `dc:title`, `dc:identifier`, `aopo:has_key_event`
  - Every `aopo:KeyEvent` must have `dc:identifier`, `dc:title`
  - Every chemical (`cheminf:000446`) must have `dc:identifier`, `dc:title`, and at least one cross-reference
  - Every gene mapping triple must use correct predicate to a valid identifier URI format
- Conformance reports: SHACL produces machine-readable validation reports (`sh:ValidationReport`); these can be stored as artifacts or committed as `data/shacl-report.ttl`

### (3) How is provenance typically handled for enriched vs source data?

**Confidence: MEDIUM** (training knowledge; community practice varies)

**File-level separation** (what is being planned, correct approach for this pipeline):
- Source-derived file: everything that comes directly from AOP-Wiki XML with no external enrichment
- Enriched files: gene mappings (text-mined + BridgeDb), chemical cross-references (BridgeDb)
- Each file gets its own VoID/pav metadata recording its source inputs and generation date

**PAV ontology** (already partially used) is the correct vocabulary:
- `pav:createdWith` — the tool/source used to generate the data (correct usage already in VoID)
- `pav:createdOn` — timestamp of generation (correct)
- `pav:importedFrom` — URI of the source dataset the data was imported from
- `pav:version` — version of the source data used

**Missing from current VoID:**
- `pav:version` for the AOP-Wiki XML (currently "aop-wiki-xml-2026-02-07" as a string, not a typed version)
- `void:triples` count
- `void:sparqlEndpoint` link
- `void:exampleResource` (enables dereferencing tools to find sample URIs)
- `pav:importedFrom` for BridgeDb (the gene/chemical enrichments are derived from BridgeDb queries, which is not recorded)

**Named graphs** (the more granular approach):
- Used by Wikidata and large knowledge graphs for triple-level provenance
- Not recommended here: adds tooling complexity, requires quad-store support, and file-level provenance is sufficient for this use case

### (4) What documentation practices are standard for RDF datasets?

**Confidence: MEDIUM** (training knowledge)

**Required (for any published Linked Data dataset):**
- VoID description with `void:triples`, `void:sparqlEndpoint`, `void:exampleResource`
- DCAT 2 metadata: `dcat:Dataset`, `dcat:distribution`, `dcat:accessURL`, `dcat:keyword`
- Namespace/prefix registry (done — `prefixes.csv` + `sh:declare` blocks in TTL)

**Expected (for academic/biomedical datasets):**
- Schema documentation: one page per entity type, listing all predicates used with their source vocabulary
- SPARQL example queries with comments explaining what they retrieve
- Changelog or release notes tied to each weekly run
- README badge showing last-generated date, triple count, QC status (partially done)

**Standard for FAIR compliance** (FindableAccessibleInteroperableReusable):
- F: persistent identifier (DOI via Zenodo — workflow exists but unverified)
- A: accessible via standard protocol (SPARQL endpoint + GitHub raw URLs — done)
- I: use of standard vocabularies (done — heavy ontology reuse)
- R: provenance metadata, license declaration — `dcterms:license` missing from current VoID

**`dcterms:license` is absent** from the current VoID. This is a blocker for Bio2RDF and EBI registry submission.

---

## MVP Recommendation for This Milestone

Prioritize in order:

1. **Correct ID mapping predicates** — fixes a semantic correctness bug that affects every downstream query using the data. Blocks shape validation.
2. **Separated pure vs enriched TTL files** — provenance clarity. Blocked by nothing once predicates are fixed.
3. **SHACL shape validation** — structural QA beyond syntax. Add 5-10 shapes for the core entity types. Use `pyshacl`. Run in CI after RDF generation.
4. **VoID enrichment** — add `void:triples`, `dcterms:license`, `void:sparqlEndpoint`, `pav:importedFrom` for BridgeDb. Low effort, high value.
5. **Schema documentation** — write once, maintain alongside predicate changes.
6. **Modular code** — precondition for reliable unit tests; enables everything else to be tested.

Defer:
- Dynamic HGNC download: useful but not blocking correctness
- Named graph provenance: overkill for this use case
- SPARQL example query expansion: helpful but not urgent

---

## Sources

This analysis draws on:
- Direct codebase inspection: `data/AOPWikiRDF.ttl`, `data/AOPWikiRDF-Genes.ttl`, `data/AOPWikiRDF-Void.ttl`, `data/ServiceDescription.ttl`
- Workflow inspection: `.github/workflows/rdfgeneration.yml`, `.github/workflows/Turtle_File_Quality_Control.yml`
- Project planning files: `.planning/PROJECT.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONCERNS.md`, `.planning/codebase/INTEGRATIONS.md`
- Training knowledge of W3C standards: SHACL (W3C Rec 2017), VoID (W3C Note 2011), DCAT 2 (W3C Rec 2020), PAV ontology, SKOS (W3C Rec 2009)
- Training knowledge of comparable biomedical RDF datasets: WikiPathways RDF, DisGeNET RDF, UniProt RDF
- **Note:** WebSearch and WebFetch were unavailable during this research session. Claims about WikiPathways/DisGeNET/UniProt predicate usage are based on training data (knowledge cutoff August 2025) and should be verified against current dataset documentation before implementation.
