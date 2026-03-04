# Technology Stack

**Analysis Date:** 2026-03-04

## Languages

**Primary:**
- Python 3.11+ - RDF generation, data processing, and validation

**Markup/Config:**
- Turtle (TTL) - RDF output format

## Runtime

**Environment:**
- Python 3.11+ (specified in GitHub Actions workflow `.github/workflows/rdfgeneration.yml`)

**Package Manager:**
- pip
- Lockfile: `requirements.txt` (pinned versions for reproducible builds)

## Frameworks

**Core Data Processing:**
- rdflib 6.3.2 - RDF graph manipulation and Turtle serialization
- pandas 2.2.2 - Data processing and analysis

**Network & HTTP:**
- requests 2.32.3 - HTTP client for BridgeDb API and external downloads
- SPARQLWrapper 2.0.0 - SPARQL endpoint queries

**Development/Analysis:**
- JupyterLab 4.0.11 - Interactive analysis notebooks (backup workflow)
- nbclient 0.8.0 - Notebook execution
- IPython 8.25.0 - Interactive Python environment
- pyvis 0.3.2 - Network visualization for RDF exploration

## Key Dependencies

**Critical:**
- rdflib 6.3.2 - Why it matters: Core RDF generation and serialization; handles Turtle syntax, triple management, and graph validation
- requests 2.32.3 - Why it matters: HTTP communication with BridgeDb API for chemical/gene identifier mapping and external data downloads
- pandas 2.2.2 - Why it matters: Data transformation and structuring before RDF conversion

**Infrastructure:**
- SPARQLWrapper 2.0.0 - SPARQL query execution for RDF data validation and analysis

## Configuration

**Environment:**
- Configured via Python script constants (`AOP-Wiki_XML_to_RDF_conversion.py` lines 35-43)
  - `BRIDGEDB_URL`: BridgeDb service endpoint (default: https://webservice.bridgedb.org/Human/ or local alternative)
  - `AOPWIKI_XML_URL`: Source XML download endpoint (https://aopwiki.org/downloads/aop-wiki-xml.gz)
  - `PROMAPPING_URL`: Protein ontology mapping file (https://proconsortium.org/download/current/promapping.txt)
  - `DATA_DIR`: Output directory (default: `data/`)

**Build:**
- No traditional build system (pure Python)
- Workflow configuration: `.github/workflows/rdfgeneration.yml`
- Dependency caching: pip cache in GitHub Actions

## Platform Requirements

**Development:**
- Python 3.11+
- pip package manager
- 2GB+ RAM for large RDF graph operations
- Internet access for external data downloads

**Production:**
- GitHub Actions runner (Ubuntu latest)
- Python 3.11+
- 90-minute execution window for weekly RDF generation
- Internet access to:
  - aopwiki.org (XML download)
  - webservice.bridgedb.org (chemical/gene identifier mapping)
  - proconsortium.org (protein mappings)
  - identifiers.org (external identifier resolution)

**Storage:**
- Typical RDF output size: 16MB main + 2MB gene extensions
- Supporting files: 3.5MB HGNC genes, 20MB protein mappings, 48MB XML source (temporary)

---

*Stack analysis: 2026-03-04*
