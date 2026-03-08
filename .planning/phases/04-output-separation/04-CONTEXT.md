# Phase 4: Output Separation - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Separate pure AOP-Wiki source triples from pipeline-enriched triples into distinct TTL files. Add a new AOPWikiRDF-Enriched.ttl containing chemical cross-references and protein ontology links. Enrich VoID metadata with a parent dataset, void:subset declarations, triple counts, licensing, and example resources. Verify that combined loading of all files reproduces the same triples as the current output.

</domain>

<decisions>
## Implementation Decisions

### File split strategy
- Extract enriched triples out of AOPWikiRDF.ttl into a new file
- **Pure AOPWikiRDF.ttl** keeps only source-derived triples: AOPs, KEs, KERs, stressors, chemical base data (dc:identifier, dc:title, cheminf properties from XML, synonyms, stressor links)
- **AOPWikiRDF-Enriched.ttl** gets ALL chemical cross-reference owl:sameAs triples (CHEBI, ChEMBL, DrugBank, PubChem, etc. from BridgeDb) AND protein ontology owl:sameAs links on biological objects (from promapping.txt)
- **AOPWikiRDF-Genes.ttl** stays as-is — already a separate enrichment file
- Enriched file contains only owl:sameAs triples (entity URI as subject, no type or base property repetition) — loading both files together gives the full picture

### Enriched file format
- Named **AOPWikiRDF-Enriched.ttl**
- Self-contained prefix declarations (all prefixes needed for the enriched triples, independently loadable)
- Turtle comment header with file description, generation date, and relationship to other files
- No RDF metadata triples about the file itself (VoID handles that)

### VoID subset declarations
- **Parent dataset** pattern: declare `:AOPWikiRDF` as parent void:Dataset with void:subset pointers to all three content files (pure, genes, enriched)
- Each subset is also a void:Dataset with its own metadata
- **void:exampleResource** entries for: AOP, Key Event, KER, Chemical, and Stressor (five entity types)
- **void:triples** counts computed dynamically at generation time (count actual triples per file after writing)
- **dcterms:license** set to CC-BY 4.0 (http://creativecommons.org/licenses/by/4.0/)
- **pav:importedFrom** on enriched file referencing BridgeDb service

### Backward compatibility
- **Clean break**: AOPWikiRDF.ttl becomes pure immediately, no transitional combined file
- Downstream consumers need to load AOPWikiRDF.ttl + AOPWikiRDF-Enriched.ttl for full cross-reference capability
- Document change in release notes / commit messages

### GitHub Actions workflow
- Add AOPWikiRDF-Enriched.ttl to the commit pattern (fourth file alongside existing three)
- Add AOPWikiRDF-Enriched.ttl to the QC validation workflow (rdflib validation of all four TTL files)

### Regression testing
- Triple count regression test: load all separated files, verify combined triple count matches pre-separation output
- Same approach as Phase 2 regression methodology

### Claude's Discretion
- Internal refactoring of writer.py to emit pure vs enriched triples
- Exact prefix set needed in the enriched file
- How to count triples efficiently (rdflib parse or line-based heuristic)
- Turtle comment header wording
- Which specific example resources to pick for void:exampleResource

</decisions>

<specifics>
## Specific Ideas

- The enriched file should be lightweight — just owl:sameAs triples, no repeated base properties
- VoID parent dataset makes "load everything" discoverable through void:subset traversal
- Dynamic triple counting ensures VoID metadata stays accurate as AOP-Wiki content grows weekly
- Clean break mirrors the project's preference for simple, non-transitional changes (unlike the Phase 3 dual-predicate approach which was a specific consumer-protection measure)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `rdf/writer.py`: Three writer functions (write_aop_rdf, write_genes_rdf, write_void_rdf) — write_aop_rdf needs splitting; write_void_rdf needs VoID enrichment
- `rdf/namespaces.py`: get_main_prefixes(), GENES_PREFIXES, VOID_PREFIXES constants — new ENRICHED_PREFIXES needed
- `pipeline.py`: STAGES list with _stage_write_aop_rdf, _stage_write_genes_rdf, _stage_write_void_rdf — add _stage_write_enriched_rdf

### Established Patterns
- Writer builds Turtle by string concatenation (not rdflib Graph) for byte-identical output
- Only rdf/writer.py imports rdflib — mapping modules stay RDF-free
- Entity data flows as plain dicts through pipeline context
- Config controls behavior via PipelineConfig fields (e.g., emit_legacy_predicates)
- Each writer function is self-contained: opens file, writes prefixes, writes triples, closes

### Integration Points
- `_stage_write_aop_rdf` in pipeline.py assembles writer_entities dict — needs modification to exclude enriched triples
- Chemical owl:sameAs triples currently emitted at writer.py lines ~425-431 — these move to enriched writer
- Protein ontology owl:sameAs triples currently emitted at writer.py lines ~373-378 — these move to enriched writer
- VoID writer needs access to triple counts from all three content writers (currently written before VoID)
- GitHub Actions: `.github/workflows/rdfgeneration.yml` and `.github/workflows/Turtle_File_Quality_Control.yml`

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-output-separation*
*Context gathered: 2026-03-08*
