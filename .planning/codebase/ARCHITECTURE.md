# Architecture

**Analysis Date:** 2026-03-04

## Pattern Overview

**Overall:** Linear ETL (Extract-Transform-Load) pipeline with staged data processing

**Key Characteristics:**
- **Extract phase**: Download AOP-Wiki XML and supporting datasets (HGNC genes, Protein Ontology)
- **Transform phase**: Parse XML into nested dictionaries, apply semantic mappings, perform biological entity enrichment
- **Load phase**: Write RDF triples to Turtle format files
- **Enrichment passes**: Multi-stage gene and chemical identifier mapping with BridgeDb and HGNC services
- **Validation layers**: XML structure validation, entity count verification, field presence checks

## Layers

**Input & Extraction Layer:**
- Purpose: Download and validate source data from remote endpoints
- Location: `AOP-Wiki_XML_to_RDF_conversion.py` (lines 289-346, Step #2)
- Contains: Download retry logic, gzip extraction, XML parsing
- Depends on: `requests` library, network connectivity
- Used by: XML parser and data extraction layer

**XML Parsing & Data Extraction Layer:**
- Purpose: Extract domain entities from AOP-Wiki XML into Python dictionaries
- Location: `AOP-Wiki_XML_to_RDF_conversion.py` (lines 347-1203, Step #3)
- Contains:
  - Entity reference extraction (AOP, KE, KER, Stressor refs)
  - Adverse Outcome Pathways parsing (lines 374-472)
  - Chemical extraction with CAS numbers (lines 474-825)
  - Stressors, Taxonomy, Key Events (lines 826-1203)
- Depends on: XML ElementTree, semantic namespace definitions
- Used by: Chemical/gene mapping, RDF output layer

**Chemical Mapping Layer:**
- Purpose: Enrich chemical entities with cross-database identifiers via BridgeDb
- Location: `AOP-Wiki_XML_to_RDF_conversion.py` (lines 477-825)
- Contains:
  - Batch BridgeDb mapping (`map_chemicals_batch`, lines 477-533)
  - Fallback individual chemical mapping (`map_chemical_individual_fallback`, lines 664-834)
  - Response parsing for multiple database formats (ChEBI, KEGG, PubChem, etc.)
- Depends on: BridgeDb HTTP service, CAS number identifiers
- Used by: RDF output for chemical entities

**RDF Output Layer (Main File):**
- Purpose: Generate primary AOP-Wiki RDF in Turtle format
- Location: `AOP-Wiki_XML_to_RDF_conversion.py` (lines 1204-1748, Step #4)
- Contains:
  - Prefix declarations (lines 1253-1283)
  - Triple-writing functions (`write_multivalue_triple`, `write_triple`)
  - Entity type sections: AOPs, KEs, KERs, taxonomy, stressors, chemicals
  - Chemical/gene identifier mapping triples (lines 1678-1748)
- Output files: `data/AOPWikiRDF.ttl`, `data/AOPWikiRDF-Void.ttl`
- Used by: Knowledge graph consumers

**Gene Mapping Layer:**
- Purpose: Text-mine KE descriptions and relationships for gene mentions, enrich with HGNC identifiers
- Location: `AOP-Wiki_XML_to_RDF_conversion.py` (lines 1785-2187, Steps #5A-#5D)
- Contains:
  - HGNC gene dictionary loading (lines 1788-1839)
  - Two-stage gene matching algorithm with false positive filtering (`map_genes_in_text_simple`, lines 108-231)
  - BridgeDb batch gene mapping (lines 1942-2107)
  - Gene annotation triple writing
- Output file: `data/AOPWikiRDF-Genes.ttl`
- Used by: Knowledge graph for gene-AOP associations

**Production Wrapper Layer:**
- Purpose: Configure and execute conversion with flexible output directory
- Location: `run_conversion.py`
- Contains: Argument parsing, static file management, script execution with CONFIG injection
- Depends on: Main conversion script
- Used by: GitHub Actions workflows, command-line invocation

## Data Flow

**Primary Conversion Flow:**

1. **Download Phase**
   - Download AOP-Wiki XML (gzip) from `https://aopwiki.org/downloads/aop-wiki-xml.gz`
   - Download Protein Ontology mappings from `https://proconsortium.org/download/current/promapping.txt`
   - Extract XML to `data/aop-wiki-xml-{YYYY-MM-DD}`

2. **Parse & Extract Phase**
   - Parse XML root and extract reference identifiers for AOP/KE/KER/Stressor
   - Build nested dictionaries: `aopdict`, `kedict`, `kerdict`, `strdict`, `chedict`
   - Extract taxonomy terms, chemicals with CAS numbers, stressors

3. **Chemical Enrichment Phase**
   - Collect unique CAS numbers from chemicals
   - Batch map CAS→database identifiers via BridgeDb (100 per request)
   - Fallback to individual API calls on batch failure
   - Parse multi-database response (ChEBI, KEGG, ChEMBL, PubChem, etc.)
   - Apply results to `chedict`

4. **RDF Generation Phase (Main File)**
   - Write RDF prefixes (AOP Ontology, PATO, Gene Ontology, Chemical Information Ontology, etc.)
   - Iterate entity dictionaries and write triples:
     - Subject: entity identifier (e.g., `aop:123`)
     - Predicates: ontology properties (e.g., `aopo:has_key_event`, `dc:title`)
     - Objects: entity data, references, or other entity IRIs
   - Output: `AOPWikiRDF.ttl` (~16MB), `AOPWikiRDF-Void.ttl` (VoID metadata)

5. **Gene Mapping Phase**
   - Load HGNC gene dictionary from `HGNCgenes.txt` (basic names + precision variants)
   - Text-mine KE descriptions and relationships for gene mentions
   - **Two-stage matching:**
     - Stage 1: Screen text with basic gene symbols (genedict1)
     - Stage 2: Match with punctuation-delimited variants (genedict2) for precision
     - Stage 3: Apply false positive filters (single-letter aliases, Roman numerals)
   - Batch map found genes to HGNC/Entrez/UniProt via BridgeDb
   - Output: `AOPWikiRDF-Genes.ttl` (~2MB)

**State Management:**

- **Dictionaries as state**: All extracted entities stored in module-level dicts
  - `aopdict[aop_id]`: AOP metadata and relationships
  - `kedict[ke_id]`: Key Event descriptions and components
  - `kerdict[ker_id]`: Key Event Relationships
  - `chedict[chem_id]`: Chemical names, CAS, identifiers
  - `strdict[str_id]`: Stressor definitions
  - `taxdict`: Taxonomy terms
  - `hgnclist`, `ncbigenelist`, `uniprotlist`: Gene identifier accumulator lists

- **Global accumulator lists**: Deduplicated identifier tracking
  - Chemical IDs: `listofchebi`, `listofchemspider`, `listofpubchem`, `listofkegg`, etc.
  - Gene IDs: `hgnclist`, `ncbigenelist`, `uniprotlist`

## Key Abstractions

**AOP Entity Model:**
- Purpose: Represent Adverse Outcome Pathways with metadata and relationships
- Examples: `aopdict` structure in lines 374-472
- Pattern: Nested dictionary with semantic RDF property names as keys
- Properties: title, description, life stage applicability, molecular initiating events, adverse outcomes, stressor links

**Key Event (KE) Entity Model:**
- Purpose: Represent biological Key Events with gene/chemical relationships
- Examples: `kedict` in lines 1067-1153
- Pattern: Dictionary with KE components (biological process, object, action) and text descriptions
- Text mining targets: Gene mentions in KE descriptions extracted via `map_genes_in_text_simple`

**Chemical Entity Model:**
- Purpose: Represent chemical stressors with multi-database identifiers
- Examples: `chedict` in lines 474-825
- Pattern: Dictionary with CAS identifier, chemical properties, and mapped database IDs
- Database coverage: ChEBI, ChemSpider, Wikidata, ChEMBL, PubChem, KEGG, LIPID MAPS, DrugBank, HMDB

**Gene Mapping Model:**
- Purpose: Text-based gene discovery and enrichment with standardized identifiers
- Implementation: Three-stage algorithm in `map_genes_in_text_simple` (lines 108-231)
  - **Stage 1 screening**: Basic gene symbols against genedict1
  - **Stage 2 precision**: Punctuation-delimited matching against genedict2
  - **Stage 3 filtering**: Remove single-letter aliases, Roman numerals, ambiguous context patterns
- Output: HGNC gene IDs with supporting Entrez/UniProt cross-references

## Entry Points

**Main Python Script:**
- Location: `AOP-Wiki_XML_to_RDF_conversion.py`
- Triggers: Direct execution or via `run_conversion.py`
- Responsibilities:
  - Orchestrate full conversion pipeline
  - Download/validate/parse XML
  - Extract and enrich entities
  - Write RDF output files

**Production Wrapper:**
- Location: `run_conversion.py`
- Triggers: GitHub Actions workflows, local command-line invocation
- Responsibilities:
  - Parse command-line arguments (--output-dir, --log-level)
  - Prepare output directory
  - Copy static files (HGNC gene database, type labels)
  - Inject configuration values into conversion script
  - Execute modified script in isolated namespace

**Jupyter Notebook (Legacy):**
- Location: `AOP-Wiki_XML_to_RDF_conversion.ipynb`
- Status: Backup fallback (preserved but not production)
- Triggers: Manual execution via `jupyter execute` or UI
- Responsibilities: Same as main script but with interactive notebook interface

## Error Handling

**Strategy:** Multi-layer validation with graceful degradation

**Patterns:**

1. **Download Phase**: Retry logic with exponential backoff
   ```python
   # 3 retries with 2^attempt second delays
   for attempt in range(max_retries):
       try: download(); return
       except RequestException:
           time.sleep(2 ** attempt)
   ```

2. **XML Parsing**: Validation of structure and entity counts
   - Check root tag and vendor-specific sections
   - Log warnings for low entity counts, don't exit

3. **Chemical Mapping**: Batch-first with fallback to sequential
   - Attempt 100-chemical batch via BridgeDb
   - On failure, retry failed chemicals individually
   - Log warnings but continue processing

4. **Gene Mapping**: Three-stage filtering with logging
   - Log false positive detections (reason: "single letter alias", "Roman numeral", etc.)
   - Log slow mappings (>1s for text processing)
   - Skip ambiguous matches, don't fail

5. **File I/O**: Ensure output directory exists, handle missing static files
   - `os.makedirs(args.output_dir, exist_ok=True)` in wrapper
   - Search multiple locations for HGNCgenes.txt and typelabels.txt

## Cross-Cutting Concerns

**Logging:**
- Framework: Python `logging` module
- Configuration: Line 52-60, StreamHandler + FileHandler to `aop_conversion.log`
- Levels: INFO for major steps, WARNING for validation issues, DEBUG for detailed processing
- Output to: Console + `aop_conversion.log` file

**Validation:**
- XML structure check (lines 234-248): Namespace, root tag, vendor-specific section
- Entity count check (lines 250-261): Minimum entity counts for AOP/KE/KER/Stressor
- Required field check (lines 263-280): Presence of critical properties
- RDF syntax: External rdflib validation in `.github/workflows/Turtle_File_Quality_Control.yml`

**External Service Integration:**
- BridgeDb: For chemical and gene identifier mapping
  - Primary: `https://webservice.bridgedb.org/Human/` (production)
  - Alternative: `http://localhost:8183/Human/` (local Docker setup)
  - Batch endpoint: `/xrefsBatch/Ca` for chemicals, gene lookup endpoints
- AOP-Wiki XML: Weekly download from `https://aopwiki.org/downloads/aop-wiki-xml.gz`
- Protein Ontology: Weekly download from `https://proconsortium.org/download/current/promapping.txt`

**Performance Optimizations:**
- Batch BridgeDb API: Process 100 chemicals per request (55x faster than sequential)
- Compiled regex patterns: HTML tag removal cached at module level (line 49)
- Set-based membership testing: Convert gene dictionaries to sets for O(1) lookup
- Mega-regex: Single compiled pattern for all gene symbol matching (if enabled)

---

*Architecture analysis: 2026-03-04*
