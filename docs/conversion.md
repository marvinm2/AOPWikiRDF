# AOP-Wiki RDF Conversion Process

This document describes how the AOP-Wiki XML data is converted to RDF, including the gene mapping algorithm, chemical mapping strategy, and output file generation.

## Pipeline Overview

The conversion pipeline transforms AOP-Wiki XML exports into four RDF/Turtle files:

1. **Download** -- The latest AOP-Wiki XML export is downloaded from `https://aopwiki.org/downloads/`.
2. **Parse** -- The XML is parsed to extract AOPs, Key Events, Key Event Relationships, Stressors, Chemicals, Taxonomies, Biological Events, and related metadata into structured dictionaries.
3. **Gene mapping** -- Key Event and KER description text is scanned for gene mentions using a three-stage algorithm (see below), producing gene associations and HGNC identifier lists.
4. **Chemical mapping** -- CAS numbers extracted from chemicals are mapped to external database identifiers via the BridgeDb batch API.
5. **Protein ontology mapping** -- Biological objects are mapped to Protein Ontology identifiers using the promapping.txt file from the PRO Consortium.
6. **RDF generation** -- Four Turtle files are written: `AOPWikiRDF.ttl` (core entities), `AOPWikiRDF-Genes.ttl` (gene associations), `AOPWikiRDF-Enriched.ttl` (cross-references), and `AOPWikiRDF-Void.ttl` (VoID metadata).

## Gene Mapping Algorithm

The gene mapping system uses a three-stage algorithm to find gene mentions in Key Event and Key Event Relationship text fields. The algorithm processes description text, biological plausibility, and empirical support fields.

### Stage 1: Screening (genedict1)

The screening dictionary `genedict1` is built from the HGNC gene data file (`HGNCgenes.txt`). For each gene entry, the dictionary stores:

- The approved gene symbol (column 1)
- The approved gene name (column 2)
- Previous symbols and aliases (remaining columns, split on ", ")

Gene clusters (symbols containing `@`) are excluded.

**How it works:** For each gene in `genedict1`, every alias is checked for a simple substring match against the text. If any alias appears in the text, the gene passes to Stage 2.

**Example:** For gene TP53 (HGNC:11998) with aliases including "p53" and "tumor protein p53", Stage 1 searches the KE description text for any of these terms. If "p53" appears anywhere in the text, the gene passes screening.

### Stage 2: Precision Matching (genedict2)

The precision dictionary `genedict2` extends each alias with punctuation-delimited variants. For each alias, all combinations of leading and trailing delimiter characters from the set `[' ', '(', ')', '[', ']', ',', '.']` are generated.

**How it works:** After Stage 1 passes a gene, Stage 2 checks whether any punctuation-bounded variant from `genedict2` appears in the text. This prevents matching gene symbols that are substrings of longer words.

**Example:** For a gene with symbol "A", `genedict2` generates variants like `" A "`, `" A,"`, `"(A)"`, `" A."`, etc. This prevents matching the letter "A" when it appears as part of normal English text, only matching when it appears as a standalone term bounded by punctuation or spaces.

### Stage 3: False Positive Filtering

After Stage 2 finds a match, four false positive filters are applied to eliminate problematic patterns:

**Filter 1: Single Letter Aliases.** Any matched alias that is a single uppercase letter (A-Z) is rejected. Many genes have single-letter aliases that are far too ambiguous for text matching.

- **Example:** PPIB has alias "B". Without this filter, every occurrence of the letter "B" bounded by punctuation would match. With the filter, PPIB alias "B" is blocked entirely.

**Filter 2: Roman Numerals.** Matched aliases that are Roman numerals (composed entirely of I, V, X) are rejected. Scientific text frequently uses Roman numerals for numbering.

- **Example:** GCNT2 has alias "II". Without this filter, text like "Complex II" or "(I-V)" would falsely match GCNT2. The Roman numeral filter blocks "II" as a Roman numeral pattern. In production, this eliminated 108 false GCNT2 occurrences.

**Filter 3: Short Symbols in Brackets.** Matched aliases of 2 characters or fewer that appear in text containing parentheses, brackets, or braces are rejected. Short symbols in parenthetical contexts are almost always scientific abbreviations rather than gene references.

**Filter 4: Gene-Specific Context Rules.** Targeted rules for known problematic patterns:

- **IV gene:** When matched alias "IV" appears near "Complex I" or "(I-V)" numbering patterns, the match is rejected.
- **II alias (GCNT2):** When "II" appears near "(I-V)" numbering or "complexes" text, the match is rejected.

### Proven Results

The false positive filtering system achieved a **14.6% reduction** in false positive gene mappings (1,398 gene occurrences eliminated):

| Gene | Alias | Before Filtering | After Filtering | Reduction |
|------|-------|-----------------|-----------------|-----------|
| GCNT2 | "II" | 108 | 0 | 100% |
| PPIB | "B" | 134 | 4 | 97% |
| IV | "IV" | 37 | 4 | 89% |

## Chemical Mapping Strategy

### CAS Identifier Extraction

Chemical entities in the AOP-Wiki XML include CAS Registry Numbers stored as the `cheminf:000446` property. The chemical mapper extracts CAS numbers from the parsed chemical dictionary (`chedict`) by reading the `cheminf:000446` property from each chemical entry.

### BridgeDb Batch API

CAS numbers are mapped to external database identifiers using the BridgeDb web service. The batch mapping endpoint (`/xrefsBatch/Ca`) is used for efficient processing.

**Batch processing flow:**

1. CAS numbers are collected from all chemical entries that have a `cheminf:000446` property.
2. Numbers are grouped into chunks of 100 (configurable `batch_size`).
3. Each chunk is sent as a POST request to the BridgeDb batch API with system code `Ca` (CAS).
4. The response is parsed to extract cross-reference identifiers grouped by system code.
5. On batch failure, the system automatically falls back to individual GET requests (`/xrefs/Ca/{cas}`) for each CAS number in the failed batch.

This batch approach provides a **55x performance improvement** over sequential individual API calls.

### Mapped External Databases

The following external databases are mapped from CAS numbers via BridgeDb:

| Database | System Code | RDF Property | Prefix |
|----------|-------------|-------------|--------|
| ChEBI | Ce | `cheminf:000407` | `chebi:` |
| ChemSpider | Cs | `cheminf:000405` | `chemspider:` |
| Wikidata | Wd | `cheminf:000567` | `wikidata:` |
| ChEMBL | Cl | `cheminf:000412` | `chembl.compound:` |
| PubChem | Cpc | `cheminf:000140` | `pubchem.compound:` |
| DrugBank | Dr | `cheminf:000406` | `drugbank:` |
| KEGG Compound | Ck/Kd | `cheminf:000409` | `kegg.compound:` |
| LIPID MAPS | Lm | `cheminf:000564` | `lipidmaps:` |
| HMDB | Ch | `cheminf:000408` | `hmdb:` |

### BridgeDb Gene Cross-References

Gene identifiers are also resolved via BridgeDb. After the three-stage gene mapping produces a list of HGNC IDs, the batch API endpoint `/xrefsBatch/H` (system code H for HGNC symbol) is called to resolve cross-references.

The process uses a `symbol_lookup` dictionary (mapping numeric HGNC ID to approved gene symbol) to convert between the internal numeric HGNC ID representation and the symbol-based queries that BridgeDb expects.

Cross-references are resolved to three target databases:

| Database | System Code | RDF Type | Prefix |
|----------|-------------|----------|--------|
| Entrez Gene | L | `edam:data_1027` | `ncbigene:` |
| Ensembl | En | `edam:data_1033` | `ensembl:` |
| UniProt | S | `edam:data_2291` | `uniprot:` |

## Output File Generation

### AOPWikiRDF.ttl

The main RDF file is built by writing Turtle triples directly as strings (not using rdflib Graph objects) to preserve exact formatting. Entity data from the parsed dictionaries is written in order: AOPs, Key Events, Biological Events, KERs, Taxonomies, Stressors, Biological Processes/Objects/Actions, Cell/Organ contexts, Chemicals, mapped chemical identifiers, mapped gene identifiers, and class labels.

### AOPWikiRDF-Genes.ttl

The genes file contains KE-to-gene and KER-to-gene mapping triples (using `edam:data_1025`), followed by gene identifier triples with `owl:sameAs` cross-references to Entrez, Ensembl, and UniProt.

### AOPWikiRDF-Enriched.ttl

The enriched file contains only `owl:sameAs` cross-reference triples linking chemicals and biological objects to external database identifiers. It does not duplicate entity type declarations or base properties.

### AOPWikiRDF-Void.ttl

The VoID metadata file describes the parent dataset (`:AOPWikiRDF`) with `void:subset` links to the three content files, plus linkset descriptions for HGNC gene data and Protein Ontology mappings. Each subset includes provenance information (creation date, source files, BridgeDb URL) and triple counts.
