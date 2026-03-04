# External Integrations

**Analysis Date:** 2026-03-04

## APIs & External Services

**BridgeDb (Identifier Mapping):**
- Service: BridgeDb webservice for chemical and gene identifier mapping
- What it's used for: Maps chemical CAS numbers to database identifiers (ChEBI, ChemSpider, DrugBank, HMDB, PubChem, etc.) and maps gene symbols to HGNC/UniProt/NCBI Gene IDs
  - SDK/Client: requests library (HTTP POST/GET)
  - Endpoint: `https://webservice.bridgedb.org/Human/` (configurable in `AOP-Wiki_XML_to_RDF_conversion.py` line 36)
  - Fallback: Local Docker BridgeDb service (http://localhost:8183/Human/)
  - Methods:
    - Batch API: `/xrefsBatch/Ca` for chemical mapping (100 CAS per request)
    - Individual endpoints for gene mapping lookups
  - Implementation: `map_chemicals_batch()` (line 477) and `map_genes_in_text_simple()` (line 108) in main script

**AOP-Wiki XML Export:**
- Service: AOP-Wiki data portal
- What it's used for: Source data for RDF generation - provides complete XML export of all AOPs, Key Events, Key Event Relationships, stressors, and chemical entities
  - Download URL: `https://aopwiki.org/downloads/aop-wiki-xml.gz`
  - Format: Gzip-compressed XML (48-50MB compressed, ~9.4GB uncompressed)
  - Update frequency: Quarterly (script runs weekly to capture latest)
  - Implementation: `download_with_retry()` (line 75) with exponential backoff

**Protein Consortium (ProMapping):**
- Service: PRotein ontology mapping service
- What it's used for: Maps biological object terms from Protein Ontology (PR) to protein database identifiers (HGNC, NCBI Gene, UniProt)
  - Download URL: `https://proconsortium.org/download/current/promapping.txt`
  - Format: Tab-separated values (20MB)
  - Usage: Maps PR: prefixed identifiers to standardized database references
  - Implementation: Downloaded in main script (line 1016), parsed in mapping loop (lines 1046-1063)

**HGNC Gene Database:**
- Service: HUGO Gene Nomenclature Committee approved gene names and symbols
- What it's used for: Gene symbol validation and approved naming for gene mapping precision filtering
  - Source: Custom download from https://www.genenames.org/download/custom/
  - Format: Tab-separated file (3.5MB, `HGNCgenes.txt`)
  - Used in: Gene precision filtering and false positive detection

**Identifiers.org (Identifier Resolution):**
- Service: Public identifier resolution service
- What it's used for: Provides stable URLs and URIs for biological and chemical identifiers
  - Prefixes used: aop/, aop.events/, aop.relationships/, aop.stressor/, cas/, chebi/, hgnc/, ncbigene/, uniprot/, chemspider/, drugbank/, etc.
  - Implementation: Referenced in `prefixes.csv` (lines 7-47) for RDF namespace declarations
  - URI resolvability: Monitored weekly via `.github/workflows/uri-resolvability-check.yml` (73% success rate as of latest check)

## Data Storage

**Databases:**
- Not applicable - project is pure RDF/graph-based

**File Storage:**
- Local filesystem only (GitHub repository)
- Output location: `data/` directory
- Generated files:
  - `data/AOPWikiRDF.ttl` - Main RDF dataset (16MB, ~3.3M triples)
  - `data/AOPWikiRDF-Genes.ttl` - Gene mapping extensions (2MB)
  - `data/AOPWikiRDF-Void.ttl` - VoID metadata and dataset descriptions (2KB)
  - `data/ServiceDescription.ttl` - SPARQL endpoint service description

**Caching:**
- GitHub Actions pip cache: `~/.cache/pip` (`.github/workflows/rdfgeneration.yml` lines 28-35)
- BridgeDb responses: Not cached (fresh mappings with each run)

## Authentication & Identity

**Auth Provider:**
- Not applicable - all external APIs are public/unauthenticated
- GitHub Actions: Uses `secrets.GITHUB_TOKEN` for repository operations (`.github/workflows/rdfgeneration.yml` line 19)

**Authorization:**
- GitHub Actions workflows use standard token for git push operations
- No API keys required for public BridgeDb, AOP-Wiki, or Identifiers.org services

## Monitoring & Observability

**Error Tracking:**
- Python logging to console and file: `aop_conversion.log` (local logging, line 57)
- GitHub Actions built-in logs and artifact storage
- Validation script produces `data/qc-status.txt` for workflow health checks

**Logs:**
- Approach: Python logging with INFO/DEBUG levels configurable via `--log-level` argument to `run_conversion.py`
- Log format: `%(asctime)s - %(levelname)s - %(message)s`
- File output: `aop_conversion.log` (persisted in repository)
- GitHub Actions: Full step-by-step logging with execution summaries

**Quality Control:**
- RDF syntax validation: `rdflib.Graph().parse()` in workflow validation step (`.github/workflows/rdfgeneration.yml` lines 68-118)
- URI pattern validation: `scripts/validation/validate_rdf_uris.py`
- URI resolvability check: `scripts/validation/test_uri_resolvability.py` (50+ URIs sampled weekly)

## CI/CD & Deployment

**Hosting:**
- GitHub repository (https://github.com/marvinm2/AOPWikiRDF)
- RDF files served via GitHub raw content and repository releases

**CI Pipeline:**
- **Primary Workflow** (`.github/workflows/rdfgeneration.yml`):
  - Trigger: Weekly schedule (Saturdays 08:00 UTC) + manual dispatch
  - Steps: Python 3.11 setup, pip cache, dependency install, script execution, TTL validation, commit/push
  - Timeout: 120 minutes per workflow
  - Output: Automatic commit with RDF files if changes detected

- **Quality Control** (`.github/workflows/Turtle_File_Quality_Control.yml`):
  - Trigger: After RDF generation completes
  - Steps: RDF syntax validation, creates `data/qc-status.txt`
  - Blocks workflow on validation failure

- **URI Resolvability Monitoring** (`.github/workflows/uri-resolvability-check.yml`):
  - Trigger: Weekly (Sundays 10:00 UTC) + manual dispatch
  - Steps: URI pattern validation, resolvability testing (5-50 samples per prefix or all)
  - Output: Badge generation, detailed markdown report
  - Performance: Supports sampling or full test (40 minutes for all URIs)

- **Backup/Legacy Workflow** (`.github/workflows/rdfgeneration-jupyter-backup.yml`):
  - Trigger: Manual dispatch only
  - Fallback to Jupyter notebook execution if Python script fails

## Environment Configuration

**Required env vars:**
- None for build/execution (all configuration via Python constants)
- `GITHUB_TOKEN`: Provided by GitHub Actions for git operations
- `SAMPLE_SIZE`: Optional input for URI testing (default: 5)
- `TEST_ALL`: Optional flag for complete URI validation

**Secrets location:**
- No API keys or secrets required
- GitHub Actions token: Built-in `secrets.GITHUB_TOKEN`

## Webhooks & Callbacks

**Incoming:**
- None - project is pull-based (downloads from external sources)

**Outgoing:**
- GitHub commit/push: Automatic commit of updated RDF files to repository
- Release artifacts: Upload to GitHub Actions artifact storage (30-day retention)
- Optional: Zenodo integration via `.github/workflows/upload-to-zenodo.yml` for permanent archival

---

*Integration audit: 2026-03-04*
