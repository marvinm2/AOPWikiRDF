# AOPWikiRDF Pipeline Modernization

## What This Is

A production pipeline that converts AOP-Wiki XML exports into RDF (Turtle format), enriching the data with gene mappings, chemical identifier cross-references, and biological ontology links. It runs weekly via GitHub Actions and serves the semantic web community working with Adverse Outcome Pathways. This initiative modernizes the pipeline's architecture, improves gene mapping quality, separates concerns in the output, and adds shape-based validation.

## Core Value

Produce accurate, well-structured RDF from AOP-Wiki XML every week — reliably and with traceable provenance for pure vs enriched content.

## Requirements

### Validated

- AOP-Wiki XML download and parsing — existing
- RDF generation for AOPs, Key Events, KERs, Chemical Stressors — existing
- Chemical identifier mapping via BridgeDb (batch + fallback) — existing
- Gene mapping with HGNC + precision filtering (14.6% FP reduction) — existing
- Weekly automated pipeline via GitHub Actions — existing
- Turtle file quality control (rdflib validation) — existing
- URI resolvability monitoring — existing
- Gene output as separate TTL file (AOPWikiRDF-Genes.ttl) — existing
- VoID metadata generation — existing
- Taxonomy support for AOP entities — existing

### Active

- [ ] Modularize monolithic conversion script into testable modules
- [ ] Rework gene mapping pipeline with dynamic HGNC and correct predicates
- [ ] Fix `skos:exactMatch` usage — use appropriate predicates for ID mappings
- [ ] Separate pure AOP-Wiki RDF from enriched/associated content into distinct TTL files
- [ ] Add ShEx/SHACL shape validation for RDF output
- [ ] Replace `exec()`/string-replacement config with proper configuration
- [ ] Write documentation covering RDF schema, conversion process, and mapping strategy
- [ ] Explore BioBERT for gene NER as future improvement path

### Out of Scope

- YARRML transition (#60-63) — deferred, separate collaboration with Saurav Kumar
- KER relationship overview extraction (#68) — deferred to future round
- Auto-generated statistics reports — not the focus; documentation is about schema and process clarity
- Mobile or web UI — this is a data pipeline, not a user-facing application
- Real-time conversion — weekly batch is the deployment model

## Context

- **Existing codebase**: ~2,300-line monolithic Python script, production since September 2025
- **Legacy backup**: Jupyter notebook preserved but not used in production
- **External dependencies**: AOP-Wiki XML downloads, BridgeDb API, HGNC gene data, Protein Ontology mappings
- **Collaboration**: YARRML research ongoing with Saurav Kumar (EUROTOX) but out of scope here
- **Related repos**: aopwiki-snorql-extended (SPARQL interface consuming the RDF)
- **GitHub issues in scope**: #64, #65, #67, #69, #52, #51
- **URI resolvability**: ~73% success rate on external URIs (monitored weekly)

## Constraints

- **Backward compatibility**: Output RDF must remain consumable by existing SPARQL endpoints and SNORQL interface
- **Weekly schedule**: Pipeline must complete within GitHub Actions time limits (Saturday 08:00 UTC)
- **External APIs**: BridgeDb availability is not guaranteed — fallback mechanisms required
- **Python ecosystem**: Stay within Python; no new language runtimes
- **No breaking changes**: Existing downstream consumers must not break during transition

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Modularize into separate Python modules | 2,300-line monolith is hard to test and maintain | — Pending |
| Separate pure vs enriched RDF into distinct files | Provenance clarity; users can choose what to consume | — Pending |
| Full gene mapping rework over incremental fix | HGNC static download + wrong predicates need holistic solution | — Pending |
| RDF output validation only (not source XML) | Focus on what we control and ship | — Pending |
| Defer YARRML transition | Separate collaboration, different timeline | — Pending |
| Defer KER overview extraction (#68) | Not priority for this round | — Pending |

---
*Last updated: 2026-03-04 after initialization*
