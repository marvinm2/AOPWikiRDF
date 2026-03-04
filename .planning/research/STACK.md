# Technology Stack — Modernization Additions

**Project:** AOPWikiRDF Pipeline Modernization
**Researched:** 2026-03-04
**Scope:** New additions only — existing stack (rdflib 6.3.2, requests, pandas, SPARQLWrapper) is not re-evaluated here

**Note on verification:** External web tools (WebSearch, WebFetch) were unavailable during this research session. All recommendations below are based on: (1) direct codebase inspection, (2) established W3C standards, (3) training knowledge through August 2025. Confidence levels reflect this. Version numbers should be verified against PyPI before pinning.

---

## 1. RDF Shape Validation — ShEx vs SHACL

### Recommendation: SHACL via `pyshacl`

Use SHACL (Shapes Constraint Language, W3C Recommendation) implemented by `pyshacl`.

**Confidence: MEDIUM** — SHACL is a W3C Recommendation; pyshacl is the dominant Python implementation; but current version and any breaking changes since August 2025 need verification.

### Rationale

**Why SHACL over ShEx:**

| Criterion | SHACL | ShEx |
|-----------|-------|------|
| W3C status | Recommendation (2017, stable) | Community Group spec (not a Recommendation) |
| Python library maturity | `pyshacl` — active, well-maintained, used in production | `PyShEx` — less active, more complex setup |
| Integration with rdflib | Native — pyshacl accepts rdflib Graph objects directly | Requires separate parsing pipeline |
| Output format | SHACL validation report as RDF (machine-readable) | Text/JSON report |
| Expressiveness for this use case | Sufficient — cardinality, datatype, pattern constraints | Slightly more expressive, but not needed here |
| Community in biomedical RDF | Both used; SHACL more common in ontology communities using OWL | ShEx dominant in Wikidata ecosystem |

**Why SHACL is correct for this project specifically:**
- The output is OWL/ontology-aligned RDF (aopo, cheminf, pato, go namespaces). SHACL was designed for this stack.
- `pyshacl` accepts rdflib Graph objects directly — zero integration friction with the existing codebase.
- SHACL validation reports are themselves RDF — they can be included in VoID metadata or committed alongside the TTL files.
- ShEx is the better choice when working with Wikidata or ShEx-centric communities. AOP-Wiki is not that context.

**Why not ShEx:**
- `PyShEx` is the primary Python library and has had activity gaps. pyshacl is more actively maintained.
- Shape Expressions validation was listed in CONCERNS.md as missing — implementing it via SHACL is straightforward; ShEx adds toolchain complexity without benefit for this use case.

### Library

| Library | Version (verify) | Purpose | Install |
|---------|-----------------|---------|---------|
| `pyshacl` | >=0.25.0 | SHACL validation against rdflib graphs | `pip install pyshacl` |

**Minimum usage pattern:**
```python
from pyshacl import validate
from rdflib import Graph

data_graph = Graph()
data_graph.parse("data/AOPWikiRDF.ttl", format="turtle")

shacl_graph = Graph()
shacl_graph.parse("shapes/aop_shapes.ttl", format="turtle")

conforms, results_graph, results_text = validate(
    data_graph,
    shacl_graph=shacl_graph,
    inference='rdfs',
    abort_on_first=False
)
```

**What to define in SHACL shapes:**
- `aopo:AdverseOutcomePathway` — required: `dcterms:title`, `dcterms:created`, `dcterms:modified`, `aopo:has_key_event`
- `aopo:KeyEvent` — required: `dc:identifier`, `dcterms:alternative`
- Chemical entities — required: `dc:identifier`, `dc:source`; if cheminf class present, matching cheminf property must be present
- Gene nodes (hgnc:*) — required: `dc:identifier`, `dc:source "HGNC"`

**Where in pipeline:** Run pyshacl after `AOPWikiRDF.ttl` is written but before `qc-status.txt` is generated. Failures should set qc-status to `not valid` and block commit.

**Confidence note:** pyshacl 0.25.x was current as of mid-2025. Verify current version with `pip index versions pyshacl` before pinning.

---

## 2. Gene Identifier Mapping Predicates — Replacing `skos:exactMatch`

### Recommendation: Use `skos:exactMatch` only for concept equivalence; use `owl:sameAs` or `dcterms:identifier` + typed literals for cross-database ID links

**Confidence: HIGH** — This is based on W3C SKOS specification semantics (stable standard since 2009) and established linked data best practices.

### What `skos:exactMatch` actually means

`skos:exactMatch` (from SKOS Simple Knowledge Organization System) asserts that two **concepts** are interchangeable in all contexts — it is a concept-level mapping predicate for thesauri and controlled vocabularies. It implies transitivity and symmetry.

**Current misuse in the codebase** (confirmed by code inspection):

1. **Line 1584** — Biological objects linked to UniProt/HGNC identifiers via `skos:exactMatch`:
   ```turtle
   <pro:000000001> skos:exactMatch <uniprot:P12345>
   ```
   This asserts two concepts in different vocabularies are identical — not correct. These are the same biological entity described in different databases.

2. **Line 1654** — Chemical entity linked to ChEBI, PubChem, ChEMBL, etc. via `skos:exactMatch`:
   ```turtle
   <chebi:12345> skos:exactMatch <pubchem:compound/67890>
   ```
   Again, these are identifier cross-references, not concept equivalence claims.

3. **Line 2165** — HGNC gene nodes linked to Ensembl/Entrez/UniProt via `skos:exactMatch`:
   ```turtle
   <hgnc:BRCA2> skos:exactMatch <ncbigene:675>
   ```
   This is an identifier cross-reference, not a concept mapping.

### Correct predicates by use case

| Current usage | Correct predicate | Rationale |
|--------------|-------------------|-----------|
| Chemical: AOP-Wiki entity → ChEBI/PubChem/ChEMBL | `owl:sameAs` | These URI-identified resources refer to the same real-world chemical — OWL identity claim is appropriate when the URI itself is the identifier |
| Biological object (Protein Ontology) → UniProt accession | `owl:sameAs` | UniProt and PRO entries for the same protein are the same individual |
| Gene (HGNC node) → Ensembl/Entrez/UniProt | `owl:sameAs` | Cross-database gene identifiers for the same gene entity |
| Any node → string identifier value | `dc:identifier` + typed literal (already used correctly) | Literal values are correctly expressed as data properties |

**Alternative: `skos:exactMatch` is acceptable when both subjects are named concepts in controlled vocabularies** (e.g., GO term matched to another ontology's equivalent concept). The current code is not doing this.

**Recommendation: Replace `skos:exactMatch` with `owl:sameAs` for all URI-to-URI cross-database identifier links.**

`owl:sameAs` is already used in the codebase at line 1746 for UniProt nodes:
```python
g.write(uniprot + '... owl:sameAs <http://purl.uniprot.org/uniprot/' + uniprot[8:] + '>')
```
This is the correct pattern. Extend it consistently.

**Secondary option — `rdfs:seeAlso`:**
If strict OWL identity semantics feel too strong (i.e., if the cross-database entries are "related" rather than "identical"), `rdfs:seeAlso` is a weaker alternative meaning "further information about this resource can be found at...". It is non-committal on identity. Use this for supplementary links (e.g., linking an HGNC node to its genenames.org page), not for cross-database identifier equivalences.

**No new libraries needed** — rdflib already has `OWL.sameAs` and `RDFS.seeAlso` as built-in namespace terms.

### Code change impact

The predicate replacement is a find-and-replace across three output sections:
1. Biological objects section (~line 1584): `skos:exactMatch` → `owl:sameAs`
2. Chemical identifiers section (~line 1654): `skos:exactMatch` → `owl:sameAs`
3. Gene identifiers section (~line 2165): `skos:exactMatch` → `owl:sameAs`

This is a **breaking change for downstream SPARQL consumers** — any query using `skos:exactMatch` will need updating. The SNORQL interface and any saved queries must be audited before shipping. This is why PROJECT.md lists it as a key decision requiring holistic handling.

---

## 3. Dynamic HGNC Gene Data Access

### Recommendation: Download from HGNC BioMart at pipeline startup (HTTP, no library required)

**Confidence: MEDIUM** — HGNC BioMart has been the standard programmatic access method for years; the URL format is stable. Verify the exact column names before implementing.

### Current problem

`HGNCgenes.txt` is a **static file** committed to the repository (3.5MB, per STACK.md). This means:
- Gene data drifts from current HGNC as weeks pass
- The file requires manual updating — no automated refresh
- `run_conversion.py` must find and copy it before the conversion runs

### Solution: Dynamic download at pipeline startup

HGNC provides a programmatic download endpoint (BioMart-style custom download). No special library needed — it's an HTTP request that returns a TSV with the same column format the existing code already parses.

**Endpoint:**
```
https://www.genenames.org/cgi-bin/download/custom?col=gd_hgnc_id&col=gd_app_sym&col=gd_app_name&col=gd_prev_sym&col=gd_aliases&col=gd_pub_acc_ids&col=gd_pub_ensembl_id&status=Approved&hgnc_dbtag=on&order_by=gd_app_sym_sort&format=text&submit=submit
```

The columns requested (`gd_hgnc_id`, `gd_app_sym`, `gd_app_name`, `gd_prev_sym`, `gd_aliases`, `gd_pub_acc_ids`, `gd_pub_ensembl_id`) correspond to the tab-delimited format the existing parser already handles (line 1816 header check: `HGNC ID`, `Approved symbol`, `Approved name`, `Previous symbols`, `Synonyms`, `Accession numbers`, `Ensembl ID`).

**Confidence note on URL:** The genenames.org custom download URL format was stable as of August 2025. Verify the exact parameter names still match before implementing.

### Implementation pattern

```python
HGNC_DOWNLOAD_URL = (
    'https://www.genenames.org/cgi-bin/download/custom'
    '?col=gd_hgnc_id&col=gd_app_sym&col=gd_app_name'
    '&col=gd_prev_sym&col=gd_aliases&col=gd_pub_acc_ids'
    '&col=gd_pub_ensembl_id&status=Approved'
    '&hgnc_dbtag=on&order_by=gd_app_sym_sort&format=text&submit=submit'
)

def download_hgnc_genes(output_path: str) -> bool:
    """Download current HGNC gene data to file."""
    try:
        response = requests.get(HGNC_DOWNLOAD_URL, timeout=60, verify=True)
        response.raise_for_status()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        logger.info(f"HGNC data downloaded: {len(response.text.splitlines())} lines")
        return True
    except requests.RequestException as e:
        logger.warning(f"HGNC download failed: {e}. Falling back to cached file.")
        return False
```

**Fallback strategy:** If the download fails (HGNC server down), fall back to the last-committed `HGNCgenes.txt`. This means keeping the static file as a cache but not as the primary source. This matches the BridgeDb pattern already in place.

**No new library required.** `requests` is already a dependency. The existing file parser is unchanged.

### Alternative: HGNC REST API

HGNC also provides a REST API (`https://rest.genenames.org/`) for individual gene lookups. This is inappropriate here — it would require one request per gene (~43,000 genes), which would be extremely slow. The bulk download is the correct approach.

---

## 4. Python Project Modularization

### Recommendation: Extract into focused modules using Python packages, preserving the existing entry point

**Confidence: HIGH** — This is standard Python packaging practice, no library dependency.

### Target module structure

The 2,281-line monolith splits cleanly into four concern boundaries identified in the codebase:

```
aopwiki_rdf/
    __init__.py
    config.py           # Configuration dataclass — replaces exec()/string-replacement
    xml_parser.py       # XML download, extraction, dictionary building
    rdf_writer.py       # Turtle output generation for core entities
    gene_mapper.py      # HGNC loading, text-matching, false positive filters
    chemical_mapper.py  # BridgeDb batch API, chemical identifier resolution
    void_generator.py   # VoID metadata generation
    validation.py       # pyshacl integration, qc-status.txt writing
```

Entry point `run_conversion.py` becomes a thin orchestrator:
```python
from aopwiki_rdf.config import Config
from aopwiki_rdf.xml_parser import download_and_parse
from aopwiki_rdf.rdf_writer import write_core_rdf
from aopwiki_rdf.gene_mapper import GeneMapper
from aopwiki_rdf.chemical_mapper import map_chemicals
from aopwiki_rdf.void_generator import write_void
from aopwiki_rdf.validation import validate_outputs
```

### Configuration: replace `exec()` with a dataclass

**Current problem (CONCERNS.md confirmed):** `run_conversion.py` reads the entire 2,281-line script as a string, does `str.replace()` on it, and calls `exec()`. This is the most fragile part of the codebase.

**Solution: `config.py` with a dataclass:**

```python
from dataclasses import dataclass, field

@dataclass
class Config:
    data_dir: str = 'data/'
    bridgedb_url: str = 'https://webservice.bridgedb.org/Human/'
    aopwiki_xml_url: str = 'https://aopwiki.org/downloads/aop-wiki-xml.gz'
    promapping_url: str = 'https://proconsortium.org/download/current/promapping.txt'
    hgnc_download_url: str = 'https://www.genenames.org/cgi-bin/download/custom?...'
    max_retries: int = 3
    request_timeout: int = 30
    log_level: str = 'INFO'
```

`run_conversion.py` becomes:
```python
import argparse
from aopwiki_rdf.config import Config
from aopwiki_rdf.pipeline import run_pipeline

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default='data/')
    parser.add_argument('--log-level', default='INFO')
    args = parser.parse_args()

    config = Config(data_dir=args.output_dir, log_level=args.log_level)
    run_pipeline(config)
```

No `exec()`. No string replacement. Config is a typed Python object.

**No new libraries required** — `dataclasses` is in the Python standard library since 3.7.

### Module boundary guidelines

| Module | What goes in it | What stays out |
|--------|----------------|---------------|
| `xml_parser.py` | `download_with_retry()`, XML element extraction, building `aopdict`/`kedict`/`kerdict`/`chedict` | RDF writing, gene matching |
| `gene_mapper.py` | `map_genes_in_text_simple()`, `is_false_positive()`, HGNC file loading/download, genedict1/genedict2 construction, BridgeDb batch gene calls | Chemical mapping, RDF writing |
| `chemical_mapper.py` | BridgeDb batch chemical calls, chemical identifier list building (`listofchebi`, etc.) | Gene mapping, RDF writing |
| `rdf_writer.py` | All `g.write(...)` calls for core entities (AOP, KE, KER, stressor, chemical, biological object) | XML parsing, mapping logic |
| `void_generator.py` | VoID metadata Turtle generation | Everything else |
| `validation.py` | pyshacl invocation, qc-status.txt writing | Generation logic |

### Testing infrastructure

**Recommendation: pytest** (already implied by the `tests/` directory structure, no new dependency beyond `pytest` itself).

Each module gets a corresponding test file:
```
tests/unit/test_xml_parser.py
tests/unit/test_gene_mapper.py
tests/unit/test_chemical_mapper.py
tests/unit/test_rdf_writer.py
tests/integration/test_full_pipeline.py   # small fixture XML
```

The `tests/unit/test_enhanced_precision.py` and `tests/integration/test_precision_fix.py` already exist and can be adapted to the new `gene_mapper.py` module without major changes.

**pytest** version: >=7.0 — use whatever is current stable. No specific version sensitivity.

---

## Recommended Additions to `requirements.txt`

```
# RDF shape validation
pyshacl>=0.25.0

# Testing (dev dependency)
pytest>=7.0
```

**No other new dependencies.** All other modernization work uses:
- Python standard library (`dataclasses`, `pathlib`)
- Existing `rdflib` (already has `OWL.sameAs` namespace)
- Existing `requests` (for HGNC download)

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Shape validation library | `pyshacl` | `PyShEx` | pyshacl is more actively maintained, integrates natively with rdflib Graph objects, SHACL is a W3C Recommendation |
| ID mapping predicate | `owl:sameAs` | `skos:exactMatch` | skos:exactMatch is for concept equivalence in KOS (thesauri), not cross-database entity identity — semantically wrong for this use case |
| ID mapping predicate | `owl:sameAs` | `rdfs:seeAlso` | rdfs:seeAlso is weaker (non-identity) — appropriate for supplementary links, not cross-database equivalences |
| HGNC access | HTTP bulk download | HGNC REST API individual lookups | REST API would require ~43k requests; bulk download is the only practical approach |
| HGNC access | HTTP bulk download | Static committed file | Static file goes stale; weekly pipeline should use current data |
| Config management | Python dataclass | YAML/JSON config file | Dataclass is simpler, typed, and requires no new library; YAML would need PyYAML |
| Config management | Python dataclass | `configparser` | configparser is flat (no nesting), not typed, and is a step down from dataclasses for modern Python |
| Python packaging | Flat package (`aopwiki_rdf/`) | `src/` layout | Either works; flat layout is simpler for a single-repo project without distribution concerns |

---

## Version Verification Checklist

These versions need confirming before pinning in `requirements.txt`:

- [ ] `pyshacl` — check `pip index versions pyshacl` for current stable
- [ ] `pytest` — check for current stable (likely 8.x as of early 2026)
- [ ] `rdflib` — current codebase uses 6.3.2; check if 7.x is available and if upgrade is beneficial (rdflib 7.x was in development as of 2025)

---

## Sources

| Claim | Source | Confidence |
|-------|--------|------------|
| SHACL is a W3C Recommendation | W3C (https://www.w3.org/TR/shacl/) | HIGH — stable standard |
| `skos:exactMatch` semantics | W3C SKOS Reference (https://www.w3.org/TR/skos-reference/) | HIGH — stable standard |
| `owl:sameAs` correct for entity identity | W3C OWL 2 Reference | HIGH — stable standard |
| pyshacl is dominant Python SHACL library | Training knowledge (Aug 2025), unverified against current PyPI | MEDIUM — verify version |
| PyShEx less maintained than pyshacl | Training knowledge (Aug 2025) | MEDIUM — verify current activity |
| HGNC BioMart download URL format | Training knowledge; genenames.org documentation | MEDIUM — verify URL parameters still current |
| rdflib natively supports pyshacl integration | Codebase uses rdflib 6.3.2; pyshacl accepts Graph objects per documented API | MEDIUM — verify compatibility with rdflib 6.x |
| Python dataclasses for config | Python 3.7+ stdlib | HIGH — stable standard library feature |
