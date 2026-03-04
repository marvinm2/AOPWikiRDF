# Codebase Structure

**Analysis Date:** 2026-03-04

## Directory Layout

```
AOPWikiRDF/
├── AOP-Wiki_XML_to_RDF_conversion.py     # Main production script (2281 lines)
├── run_conversion.py                     # Production wrapper with configurable output
├── AOP-Wiki_XML_to_RDF_conversion.ipynb  # Legacy Jupyter notebook (backup)
├── AOP-Wiki_stats.ipynb                  # Statistics and analysis notebook
│
├── data/                                 # Primary input/output directory
│   ├── AOPWikiRDF.ttl                   # Main RDF output (~16MB)
│   ├── AOPWikiRDF-Genes.ttl             # Gene-focused RDF (~2MB)
│   ├── AOPWikiRDF-Void.ttl              # VoID metadata file
│   ├── ServiceDescription.ttl           # SPARQL endpoint metadata
│   ├── HGNCgenes.txt                    # HGNC gene dictionary (3.5MB)
│   ├── promapping.txt                   # Protein Ontology mappings (20MB+)
│   ├── typelabels.txt                   # Entity type labels
│   ├── qc-status.txt                    # Quality control validation result
│   └── aop-wiki-xml-{YYYY-MM-DD}        # Downloaded XML (temporary, auto-deleted)
│
├── tests/                                # Test framework
│   ├── unit/                            # Unit tests for functions
│   │   ├── test_enhanced_precision.py   # False positive filtering tests
│   │   ├── test_batch_bridgedb.py       # Batch API functionality
│   │   ├── test_batch_chemical_mapping.py
│   │   └── test_improved_batch_chemical.py
│   ├── integration/                     # End-to-end workflow tests
│   │   ├── test_precision_fix.py        # Two-stage gene mapping validation
│   │   ├── test_ke888_current.py        # Specific KE gene mappings
│   │   ├── test_mega_regex.py           # Performance test
│   │   ├── test_mega_simple.py          # Simplified validation
│   │   ├── test_scaling.py              # Scaling performance tests
│   │   └── test_chemical_batch_integration.py
│   ├── debug/                           # Troubleshooting scripts
│   │   ├── debug_false_positives.py     # Analyze false positive genes
│   │   ├── debug_jupyter_algorithm.py   # Compare implementations
│   │   ├── debug_batch_response.py      # BridgeDb response debugging
│   │   ├── debug_fmn1.py                # Gene mapping investigation
│   │   ├── debug_missing_genes.py       # Missing gene analysis
│   │   └── analyze_chemical_volume.py
│   ├── validation/                      # Validation tools
│   │   └── validate_gene_mapping.py     # Gene mapping validation
│   └── README.md                        # Test framework documentation
│
├── scripts/                              # Utility scripts
│   └── validation/
│       └── validate_rdf_uris.py         # Check URI resolvability
│
├── .github/workflows/                   # GitHub Actions CI/CD
│   ├── rdfgeneration.yml                # Main weekly RDF generation (Python script)
│   ├── rdfgeneration-jupyter-backup.yml # Fallback Jupyter generation
│   ├── test-python-conversion.yml       # Python conversion testing
│   ├── Turtle_File_Quality_Control.yml  # RDF syntax validation
│   ├── uri-resolvability-check.yml      # External URI monitoring
│   └── upload-to-zenodo.yml             # Data archive upload
│
├── SPARQLQueries/                       # Example SPARQL queries
│   ├── SPARQLqueries                    # Query examples
│   └── Federated queries                # Federated SPARQL patterns
│
├── badges/                               # Status badges
│   └── [Generated badge SVGs]
│
├── paper-materials/                     # Academic paper artifacts
│   ├── data/
│   ├── paper figures/
│   │   └── nocolor/
│   └── Paper revision/
│
├── production-rdf-backup/               # Previous production RDF files
│   ├── AOPWikiRDF.ttl
│   ├── AOPWikiRDF-Genes.ttl
│   ├── AOPWikiRDF-Void.ttl
│   └── ServiceDescription.ttl
│
├── .planning/                           # GSD planning documents
│   └── codebase/
│
├── requirements.txt                     # Python dependencies
├── README.md                            # Project documentation
├── CLAUDE.md                            # Claude Code instructions (local)
└── TESTING.md                           # Testing framework guide
```

## Directory Purposes

**Root Level:**
- Purpose: Main Python scripts and configuration
- Contains: Production conversion script, wrapper script, Jupyter notebooks, configuration files
- Key files: `AOP-Wiki_XML_to_RDF_conversion.py`, `run_conversion.py`

**`data/` Directory:**
- Purpose: Central input/output repository for conversion pipeline
- Contains:
  - Input files: HGNCgenes.txt (gene dictionary), promapping.txt (Protein Ontology), typelabels.txt
  - Output files: AOPWikiRDF.ttl (main RDF), AOPWikiRDF-Genes.ttl (gene RDF), AOPWikiRDF-Void.ttl (metadata)
  - Temporary files: Downloaded XML (auto-deleted after extraction)
  - Quality control: qc-status.txt (validation results)
- Generated: Yes (by conversion script)
- Committed: Selectively (outputs committed, temporary files excluded)

**`tests/` Directory:**
- Purpose: Comprehensive testing framework with organized test types
- Contains: Unit tests, integration tests, debug scripts, validation tools
- Key structure:
  - `unit/`: Individual function tests
  - `integration/`: Workflow and component tests
  - `debug/`: Investigation and comparison scripts
  - `validation/`: Comprehensive analysis tools
- Generated: No (source code)
- Committed: Yes (tracked in git)

**`scripts/validation/` Directory:**
- Purpose: Standalone validation utilities
- Contains: `validate_rdf_uris.py` for checking external URI resolution
- Generated: No (source code)
- Committed: Yes

**`.github/workflows/` Directory:**
- Purpose: GitHub Actions CI/CD automation
- Contains:
  - `rdfgeneration.yml`: Weekly Python script execution (production)
  - `Turtle_File_Quality_Control.yml`: RDF syntax validation
  - `uri-resolvability-check.yml`: URI resolution monitoring
  - Other supporting workflows
- Generated: No (source code)
- Committed: Yes

**`SPARQLQueries/` Directory:**
- Purpose: Reference SPARQL query examples
- Contains: Query templates for federation, specific entity lookups
- Generated: No (documentation)
- Committed: Yes

**`paper-materials/` Directory:**
- Purpose: Academic publication support files
- Contains: Data, figures, revisions
- Generated: Yes (outputs from analysis)
- Committed: Yes (paper artifacts)

**`production-rdf-backup/` Directory:**
- Purpose: Archive of previous production RDF outputs
- Contains: Historical versions of main RDF files
- Generated: Yes (by versioning process)
- Committed: Yes

**`.planning/` Directory:**
- Purpose: GSD orchestrator documentation
- Contains: Architecture, structure, conventions analysis documents
- Generated: Yes (by `/gsd:map-codebase`)
- Committed: No (created during planning)

## Key File Locations

**Entry Points:**
- `AOP-Wiki_XML_to_RDF_conversion.py`: Main linear script, runs full pipeline end-to-end
- `run_conversion.py`: Production wrapper, configures and executes main script
- `AOP-Wiki_XML_to_RDF_conversion.ipynb`: Legacy Jupyter alternative (backup only)

**Configuration:**
- `requirements.txt`: Python package dependencies (rdflib, requests, pandas)
- `.github/workflows/rdfgeneration.yml`: Weekly execution schedule (Saturdays 08:00 UTC)
- `CLAUDE.md`: Local development guidelines (not committed)

**Core Logic:**
- `AOP-Wiki_XML_to_RDF_conversion.py` sections:
  - Lines 1-60: Imports and configuration
  - Lines 62-281: Helper and validation functions
  - Lines 289-346: XML download and extraction
  - Lines 347-1203: Entity extraction (Step #3)
  - Lines 1204-1748: RDF output generation (Step #4)
  - Lines 1785-2187: Gene mapping (Step #5)

**Testing:**
- `tests/unit/test_enhanced_precision.py`: Gene false positive filtering tests
- `tests/integration/test_precision_fix.py`: Two-stage gene matching validation
- `tests/validation/validate_gene_mapping.py`: Comprehensive gene analysis

**Output Files:**
- `data/AOPWikiRDF.ttl`: Primary AOP-Wiki RDF knowledge graph
- `data/AOPWikiRDF-Genes.ttl`: Gene-centric RDF with text-mined associations
- `data/AOPWikiRDF-Void.ttl`: VoID (Vocabulary of Interlinked Datasets) metadata

## Naming Conventions

**Files:**
- Main scripts: `[Purpose]_[Format].py` (e.g., `AOP-Wiki_XML_to_RDF_conversion.py`)
- Test files: `test_[feature].py` (e.g., `test_enhanced_precision.py`) or `debug_[issue].py`
- Data files: `[Name].[format]` (e.g., `AOPWikiRDF.ttl`, `HGNCgenes.txt`)
- Temporary downloads: `aop-wiki-xml-{YYYY-MM-DD}` (date-based, auto-deleted)
- Notebooks: `[Purpose].ipynb` (e.g., `AOP-Wiki_stats.ipynb`)

**Directories:**
- Functional groups: lowercase with dash separator (e.g., `paper-materials`, `production-rdf-backup`)
- Standard test structure: `unit/`, `integration/`, `debug/`, `validation/` subdirectories
- Date-based: None (uses per-run temporary files instead)
- Hidden/special: Leading dot for GitHub/planning (`.github`, `.planning`)

**Python Variables & Functions:**
- Dictionaries: lowercase with suffix (e.g., `aopdict`, `kedict`, `chedict`)
- Lists: pluralized descriptive (e.g., `listofchebi`, `hgnclist`, `ncbigenelist`)
- Functions: snake_case (e.g., `map_genes_in_text_simple`, `validate_xml_structure`)
- Constants: UPPERCASE (e.g., `BRIDGEDB_URL`, `DATA_DIR`, `REQUEST_TIMEOUT`)

## Where to Add New Code

**New Feature (Entity Type Mapping):**
- Primary code: `AOP-Wiki_XML_to_RDF_conversion.py` Step #3 section (lines 347-1203)
- Pattern: Create extraction function, add to entity dictionary during XML parsing
- Output: Add RDF writing section in Step #4 (lines 1204-1748)
- Tests: Create in `tests/integration/test_[feature].py`

**New Component/Module (Reusable Utility):**
- Implementation: Extract as standalone function in `AOP-Wiki_XML_to_RDF_conversion.py`
- Pattern: Prefix with verb (e.g., `validate_`, `map_`, `download_`, `write_`)
- Tests: Create in `tests/unit/test_[component].py`
- Example: `map_genes_in_text_simple` (line 108), `download_with_retry` (line 75)

**Utilities (Standalone Scripts):**
- Location: `scripts/validation/` for quality/audit tools
- Pattern: Descriptive filename (e.g., `validate_rdf_uris.py`)
- Can be tested via: `tests/validation/` directory

**Workflows (CI/CD Automation):**
- Location: `.github/workflows/[purpose].yml`
- Pattern: YAML GitHub Actions syntax, triggers defined in `on:` section
- Main production: `rdfgeneration.yml` (weekly schedule + workflow completion triggers)

**Tests:**
- Unit tests: `tests/unit/test_[function].py` - isolated function tests
- Integration tests: `tests/integration/test_[workflow].py` - end-to-end scenarios
- Debug scripts: `tests/debug/debug_[issue].py` - investigation tools
- Validation: `tests/validation/validate_[system].py` - comprehensive analysis

**Documentation:**
- Local guidelines: `CLAUDE.md` (not committed, per project policy)
- Test guide: `tests/README.md` (in version control)
- Inline: Jupyter notebooks for exploratory code or complex workflows

## Special Directories

**`.ipynb_checkpoints/`:**
- Purpose: Jupyter notebook version control (auto-generated)
- Generated: Yes (by Jupyter)
- Committed: No (in .gitignore)

**`data-test/` and `test-rdf-files/data-test/`:**
- Purpose: Test data for development and validation
- Contains: RDF outputs for testing against
- Generated: Yes (test runs)
- Committed: Selectively

**`production-rdf-backup/`:**
- Purpose: Historical archive of production outputs
- Use: Fallback/comparison for validation
- Committed: Yes (versioned backups)

**`.claude/`:**
- Purpose: Reserved for local Claude development files
- Generated: No (empty or local only)
- Committed: No

---

*Structure analysis: 2026-03-04*
