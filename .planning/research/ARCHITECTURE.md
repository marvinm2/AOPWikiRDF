# Architecture Patterns

**Domain:** Biomedical RDF generation pipeline (XML → enriched Turtle)
**Researched:** 2026-03-04
**Confidence:** HIGH — based on direct code analysis of the 2,281-line production script plus established Python packaging patterns

---

## Recommended Architecture

Transform the monolithic `AOP-Wiki_XML_to_RDF_conversion.py` into a package with clearly bounded modules. The pipeline remains linear ETL, but each stage becomes an independently testable unit with explicit inputs and outputs.

### Target Package Layout

```
aopwiki_rdf/                          # Python package (src layout recommended)
├── __init__.py
├── config.py                         # Pydantic/dataclass config model
├── pipeline.py                       # Orchestrator — calls modules in order
│
├── fetcher/
│   ├── __init__.py
│   └── downloader.py                 # download_with_retry, XML/Protein Ontology fetch
│
├── parser/
│   ├── __init__.py
│   ├── xml_parser.py                 # ElementTree parsing → entity dicts
│   └── models.py                     # Typed dataclasses for AOP, KE, KER, Chemical, etc.
│
├── mapping/
│   ├── __init__.py
│   ├── chemical_mapper.py            # BridgeDb batch + fallback for CAS → multi-DB IDs
│   └── gene_mapper.py                # HGNC dict loading + three-stage text mining
│
├── rdf/
│   ├── __init__.py
│   ├── namespaces.py                 # Prefix definitions (loaded from prefixes.csv)
│   ├── writer_core.py                # write_triple, write_multivalue_triple helpers
│   ├── writer_aop.py                 # Pure AOP-Wiki triples: AOPs, KEs, KERs, stressors
│   └── writer_enriched.py            # Enriched triples: gene associations, chemical xrefs
│
├── validation/
│   ├── __init__.py
│   ├── xml_validator.py              # validate_xml_structure, validate_entity_counts
│   └── rdf_validator.py              # rdflib-based Turtle syntax check
│
└── void_generator.py                 # VoID metadata file generation

run_conversion.py                     # Entry point — replaced by proper CLI (no exec())
```

### Why src Layout

Use `src/aopwiki_rdf/` rather than `aopwiki_rdf/` at the project root. The src layout prevents accidental import of the uninstalled package during test runs (a silent correctness bug common in data pipelines). Install with `pip install -e .` for development; the package is then importable everywhere including tests.

---

## Component Boundaries

Each component owns a clear data contract. Nothing outside the component touches its internals.

| Component | Responsibility | Inputs | Outputs | Must NOT do |
|-----------|---------------|--------|---------|-------------|
| `config.py` | Hold all runtime configuration | CLI args, env vars | `PipelineConfig` dataclass | I/O, network calls |
| `fetcher/downloader.py` | Fetch remote resources reliably | URLs from config | Local file paths | Parse content |
| `parser/xml_parser.py` | Convert AOP-Wiki XML to typed dicts | XML file path | `aopdict`, `kedict`, `kerdict`, `chedict`, `strdict`, `taxdict` | Network calls, RDF writing |
| `parser/models.py` | Define entity data structures | — | Typed dataclasses for each entity type | Business logic |
| `mapping/chemical_mapper.py` | Enrich chemicals with cross-DB identifiers | `chedict` (CAS numbers), BridgeDb URL | Updated `chedict` with multi-DB xrefs | XML parsing, RDF writing |
| `mapping/gene_mapper.py` | Text-mine KE/KER text for gene mentions | `kedict`/`kerdict` descriptions, HGNC file path | Gene-to-entity mapping dict | BridgeDb chemical mapping, RDF writing |
| `rdf/writer_core.py` | Low-level Turtle serialisation helpers | File handle, predicate/value pairs | Written bytes | Entity logic, mapping calls |
| `rdf/writer_aop.py` | Emit pure AOP-Wiki triples | `aopdict`, `kedict`, `kerdict`, `strdict`, `taxdict`, `PipelineConfig` | `AOPWikiRDF.ttl` | Any enrichment data |
| `rdf/writer_enriched.py` | Emit enrichment triples only | Gene mapping results, chemical xref results, `PipelineConfig` | Content appended to `AOPWikiRDF.ttl` + `AOPWikiRDF-Genes.ttl` | Core AOP-Wiki triples |
| `validation/xml_validator.py` | Check parsed XML before processing | `root` element, entity count dict | Boolean + warnings | Downstream pipeline logic |
| `validation/rdf_validator.py` | Check generated Turtle files | File paths | Boolean + error messages | XML or mapping logic |
| `void_generator.py` | Generate VoID metadata | Entity counts, output file paths, date | `AOPWikiRDF-Void.ttl` | Entity parsing |
| `pipeline.py` | Orchestrate the full run | `PipelineConfig` | Exit code | Any entity-level logic |

---

## Data Flow

The pipeline is strictly one-directional. Data flows forward; no module reaches back into an earlier stage.

```
[Remote sources]
        |
        v
fetcher/downloader.py
  - AOP-Wiki XML (gzip)
  - Protein Ontology promapping.txt
        |
        v
parser/xml_parser.py
  Produces: aopdict, kedict, kerdict, chedict, strdict, taxdict
        |
        +------ validation/xml_validator.py  (validate before enrichment)
        |
        v
mapping/chemical_mapper.py
  Input:  chedict (CAS numbers)
  Calls:  BridgeDb /xrefsBatch/Ca (100 per request)
  Output: chedict updated with ChEBI, KEGG, PubChem, ChEMBL, etc.
        |
        v
mapping/gene_mapper.py
  Input:  kedict + kerdict (description text)
  Loads:  HGNCgenes.txt → genedict1, genedict2
  Runs:   three-stage text-mining + false positive filter
  Calls:  BridgeDb /xrefsBatch/H (100 per request)
  Output: gene_associations: {ke_id: [hgnc_ids], ker_id: [hgnc_ids]}
          gene_xrefs: {hgnc_id: {Entrez, UniProt, Ensembl}}
        |
        +------ Split: pure vs enriched
        |           |
        v           v
rdf/writer_aop.py   rdf/writer_enriched.py
  AOPWikiRDF.ttl    AOPWikiRDF-Genes.ttl
  (pure AOP data)   (gene associations + chemical xrefs)
        |
        v
void_generator.py
  AOPWikiRDF-Void.ttl
        |
        v
validation/rdf_validator.py
  Reads all .ttl files via rdflib
  Writes data/qc-status.txt
```

### Pure vs Enriched Separation

This is a required architectural decision (PROJECT.md active requirement). The split point is after enrichment completes but before RDF writing:

- **Pure RDF** (`AOPWikiRDF.ttl`): Only triples derivable directly from the AOP-Wiki XML. No text-mined gene associations, no BridgeDb-derived chemical cross-references. A consumer can trust this reflects the AOP-Wiki database as-is.

- **Enriched RDF** (`AOPWikiRDF-Genes.ttl` and chemical xref triples): Derived assertions, not asserted in the source XML. These carry different provenance. Gene associations are text-mined (heuristic), chemical xrefs come from BridgeDb (computed mapping).

The `rdf/writer_aop.py` module must not import from `mapping/` at all — this enforces the boundary at the import level, not just by convention.

---

## Configuration: Replacing exec()

The current `run_conversion.py` uses string replacement + `exec()` to inject `DATA_DIR` and log level into the monolith. This is the highest-priority thing to eliminate.

### Recommended Pattern: Dataclass Config

```python
# aopwiki_rdf/config.py
from dataclasses import dataclass, field
import os

@dataclass
class PipelineConfig:
    data_dir: str = "data/"
    log_level: str = "INFO"
    bridgedb_url: str = "https://webservice.bridgedb.org/Human/"
    aopwiki_xml_url: str = "https://aopwiki.org/downloads/aop-wiki-xml.gz"
    promapping_url: str = "https://proconsortium.org/download/current/promapping.txt"
    max_retries: int = 3
    request_timeout: int = 30
    bridgedb_chunk_size: int = 100
    hgnc_filename: str = "HGNCgenes.txt"

    def rdf_output_path(self, filename: str) -> str:
        return os.path.join(self.data_dir, filename)
```

Every module receives a `PipelineConfig` instance. No module reads environment variables or parses CLI args — that is the entry point's job only.

```python
# run_conversion.py  (new, clean entry point)
import argparse
from aopwiki_rdf.config import PipelineConfig
from aopwiki_rdf.pipeline import run

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="data/")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--bridgedb-url", default=None)
    args = parser.parse_args()

    config = PipelineConfig(
        data_dir=args.output_dir,
        log_level=args.log_level,
    )
    if args.bridgedb_url:
        config.bridgedb_url = args.bridgedb_url

    run(config)

if __name__ == "__main__":
    main()
```

This eliminates the `exec()` antipattern entirely. Tests can now construct `PipelineConfig` with custom values without touching the filesystem.

**Do not use Pydantic** for this config unless it is already a dependency — it would add a heavyweight dependency for a simple dataclass. Use `@dataclass` from the standard library.

---

## Patterns to Follow

### Pattern 1: Pipeline Orchestrator with Explicit Data Handoffs

The `pipeline.py` orchestrator makes data handoffs explicit. Each stage receives what it needs as arguments and returns a typed result.

```python
# aopwiki_rdf/pipeline.py
from aopwiki_rdf.config import PipelineConfig
from aopwiki_rdf.fetcher.downloader import fetch_all_sources
from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml
from aopwiki_rdf.mapping.chemical_mapper import enrich_chemicals
from aopwiki_rdf.mapping.gene_mapper import mine_genes
from aopwiki_rdf.rdf.writer_aop import write_aop_rdf
from aopwiki_rdf.rdf.writer_enriched import write_enriched_rdf
from aopwiki_rdf.void_generator import write_void
from aopwiki_rdf.validation.rdf_validator import validate_outputs

def run(config: PipelineConfig) -> int:
    paths = fetch_all_sources(config)
    entities = parse_aopwiki_xml(paths.xml_file, config)
    entities = enrich_chemicals(entities, config)
    gene_data = mine_genes(entities, config)
    write_aop_rdf(entities, config)
    write_enriched_rdf(entities, gene_data, config)
    write_void(entities, config)
    ok = validate_outputs(config)
    return 0 if ok else 1
```

Every intermediate value is named. No global state. Test any stage by constructing inputs directly.

### Pattern 2: Typed Entity Models Instead of Nested Dicts

Replace bare `dict` entity storage with dataclasses. This prevents key-name typos that currently go undetected until runtime.

```python
# aopwiki_rdf/parser/models.py
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class KeyEvent:
    id: str
    title: str
    description: str = ""
    biological_process: Optional[str] = None
    biological_object: Optional[str] = None
    gene_ids: List[str] = field(default_factory=list)  # populated by gene_mapper
```

The parser returns `dict[str, KeyEvent]` instead of `dict[str, dict]`. Type checkers and tests can then verify correctness.

### Pattern 3: Dependency Injection for External Services

Both BridgeDb callers (chemical and gene mapping) and the downloader talk to external services. Pass the service URL via config rather than hardcoding it.

```python
def enrich_chemicals(
    entities: EntitySet,
    config: PipelineConfig,
) -> EntitySet:
    batch_url = config.bridgedb_url + "xrefsBatch/Ca"
    ...
```

In tests, point `config.bridgedb_url` at a local mock server or use `unittest.mock.patch("requests.post")` — no production network calls required.

### Pattern 4: Context-Manager File Handling for RDF Output

Current code uses `open()` with manual `close()` calls at the end of the script. Use context managers to guarantee file closure even on exception.

```python
def write_aop_rdf(entities: EntitySet, config: PipelineConfig) -> None:
    output_path = config.rdf_output_path("AOPWikiRDF.ttl")
    with open(output_path, "w", encoding="utf-8") as rdf_file:
        _write_prefixes(rdf_file, config)
        _write_aops(rdf_file, entities.aops)
        _write_key_events(rdf_file, entities.key_events)
        ...
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Module-Level Script Execution

**What:** Current script runs code at the module top level (lines 289–2281 execute on import).
**Why bad:** Importing any function from the script triggers the entire pipeline. Tests cannot import individual functions without running a full conversion.
**Instead:** All executable logic goes inside functions. Only `if __name__ == "__main__":` triggers execution.

### Anti-Pattern 2: Global Accumulator Lists as Shared State

**What:** `hgnclist`, `listofchebi`, `ncbigenelist`, etc. are module-level lists that accumulator functions append to.
**Why bad:** Tests must reset global state between runs. Parallel pipeline stages become impossible. State is implicit.
**Instead:** Pass accumulator containers as function arguments or return them as values. Each pipeline run gets its own clean state.

### Anti-Pattern 3: String-Replace Configuration Injection

**What:** `run_conversion.py` reads the script as text, replaces `DATA_DIR = 'data/'`, then `exec()`s the modified string.
**Why bad:** Brittle (breaks if the string format changes), bypasses Python's import system, makes debugging nearly impossible (stack traces reference a synthetic filename), prevents static analysis.
**Instead:** `PipelineConfig` dataclass passed to every function (see Pattern above).

### Anti-Pattern 4: Mixing Pure and Enriched Triple Writing in One Pass

**What:** Currently, chemical xref triples and gene triples are written intermixed with core AOP-Wiki triples in a single file pass.
**Why bad:** Impossible to produce a pure-provenance file without a second filtering pass. Violates the stated requirement to separate pure from enriched content.
**Instead:** Two separate writer modules: `writer_aop.py` (pure, no imports from `mapping/`) and `writer_enriched.py` (enrichment only, reads mapping results).

### Anti-Pattern 5: Importing Inside Functions

**What:** `map_genes_in_text_simple` does `import time` and `import re` inside the function body (line 118–119).
**Why bad:** Imports inside hot-path functions (called once per KE) add repeated overhead and obscure dependencies.
**Instead:** All imports at the module top level.

---

## Suggested Build Order (Dependency Graph)

Build in this sequence because each step's output is the next step's input.

```
1. config.py
   No dependencies. Everything else depends on this.

2. parser/models.py
   No dependencies. Defines data contracts used by all other modules.

3. fetcher/downloader.py
   Depends on: config.py
   Provides: file paths to XML and promapping

4. parser/xml_parser.py
   Depends on: config.py, parser/models.py
   Provides: EntitySet (typed entity container)

5. validation/xml_validator.py
   Depends on: parser/models.py
   Can be built in parallel with step 4.

6. mapping/chemical_mapper.py
   Depends on: config.py, parser/models.py
   Can be built independently of gene_mapper.

7. mapping/gene_mapper.py
   Depends on: config.py, parser/models.py
   Can be built in parallel with step 6.

8. rdf/namespaces.py + rdf/writer_core.py
   Depends on: config.py only
   Provides: helper functions for all RDF writers

9. rdf/writer_aop.py
   Depends on: rdf/writer_core.py, parser/models.py, rdf/namespaces.py
   Must NOT depend on mapping/ modules (enforces pure/enriched boundary)

10. rdf/writer_enriched.py
    Depends on: rdf/writer_core.py, parser/models.py, mapping results
    Builds after writer_aop.py so the file separation pattern is already established.

11. void_generator.py
    Depends on: config.py, entity counts from parser/models.py

12. validation/rdf_validator.py
    Depends on: config.py only (reads output files via rdflib)

13. pipeline.py
    Depends on: all modules above
    Final integration step.

14. run_conversion.py (entry point)
    Depends on: config.py, pipeline.py
```

Practical milestone mapping:
- **Milestone 1 (Foundation):** Steps 1–5 — config, models, fetcher, parser, XML validation
- **Milestone 2 (Mapping):** Steps 6–7 — chemical and gene mapping as isolated modules with tests
- **Milestone 3 (RDF Output):** Steps 8–10 — pure and enriched RDF writers with the hard boundary
- **Milestone 4 (Completion):** Steps 11–14 — VoID, RDF validation, orchestrator, CLI

---

## Scalability Considerations

The pipeline runs once per week on GitHub Actions free tier. Scalability means "fits within Actions time limits reliably," not horizontal scaling.

| Concern | Current | Modular Target | Notes |
|---------|---------|---------------|-------|
| Gene mapping speed | ~28 min baseline, optimised with mega-regex | No change — same algorithm, now in an isolated module | Time budget is the same |
| BridgeDb reliability | Batch + fallback already implemented | Config-injectable URL makes local BridgeDb easy to use for testing | No regression |
| Memory | All entity dicts held in memory | Dataclasses use same memory profile | No regression |
| Test isolation | None — tests import functions from 2,281-line script | Each module importable independently | Major improvement |
| CI reproducibility | exec()-based injection is fragile | PipelineConfig eliminates fragility | Major improvement |

---

## Sources

- Direct code analysis of `AOP-Wiki_XML_to_RDF_conversion.py` (2,281 lines, 2026-03-04) — HIGH confidence
- Direct code analysis of `run_conversion.py` (69 lines, 2026-03-04) — HIGH confidence
- `.planning/codebase/ARCHITECTURE.md` — HIGH confidence (prior codebase analysis)
- `.planning/PROJECT.md` — HIGH confidence (project requirements)
- Python standard library `dataclasses` module documentation — HIGH confidence (standard library, stable)
- Python src layout convention: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/ — HIGH confidence
