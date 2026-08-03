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

## Per-AOP Licence Metadata

Each AOP in the source XML carries a `<wiki-license>` element inside its `<status>` block, with one of two codes:

- `BY-SA` -- the AOP has been published under Creative Commons Attribution-ShareAlike 4.0 (CC-BY-SA 4.0). This is the default since AOP-Wiki Release 2.6 (2023-04-29).
- `ARR` -- the AOP is still under All Rights Reserved during its 30-day grace period. Upstream activated automatic ARR-to-CC-BY-SA conversion on 2026-04-30.

The parser captures this value and the RDF writer emits a `dcterms:license` triple per AOP, mapping to a stable rights URI:

| `<wiki-license>` code | Emitted `dcterms:license` URI |
|---|---|
| `BY-SA` | `<https://creativecommons.org/licenses/by-sa/4.0/>` |
| `ARR`   | `<https://rightsstatements.org/page/InC/1.0/>` |

Older XML snapshots that predate Release 2.6 omit the `<wiki-license>` element entirely; for those AOPs no `dcterms:license` triple is emitted. Downstream consumers can filter or partition AOPs by licence using simple SPARQL queries (see `docs/sparql-examples.md`, query 11).

### Optional ARR filter

For strict CC-BY-SA-only release builds, the pipeline supports an opt-in filter:

```python
from aopwiki_rdf.config import PipelineConfig
config = PipelineConfig(filter_arr_aops=True)
```

When enabled, ARR-licensed AOPs are dropped from the AOP dictionary between the parse and write stages. The filter is **AOP-only**: Key Events, KERs, and Stressors are left untouched, because the upstream schema asserts licence at AOP level only. Default is `False` -- the primary mechanism is per-AOP `dcterms:license` transparency, not exclusion.

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

### Stage 2: Boundary-bounded matching (Aho-Corasick)

Matching uses an Aho-Corasick automaton (`mapping/automaton.py`) built once per run from `{token: gene}`. Each text is scanned **once**, in time proportional to its length rather than to the size of the dictionary.

A match counts only when the characters immediately before and after it are delimiters, from the set `[' ', '(', ')', '[', ']', ',', '.']` — so `AR` matches in `"(AR)"` but not inside `ARID1A`. **The start and end of the text also count as boundaries.**

This replaced a dictionary named `genedict2` that pre-expanded every token into all 49 combinations of leading and trailing delimiter, and a loop that tested all ~45,000 genes against every text.

| | expanded dictionary + loop | automaton |
|---|---:|---:|
| dictionary build | 37 s, 510 MB peak | 1.0 s, 23 MB peak |
| stored entries | 7,383,026 variants | 146,633 tokens / 563,036 states |
| corpus scan (2,737 texts) | 505 s | 2.8 s |

`genedict2` is no longer built. `build_gene_dicts(..., build_precision_dict=True)` still produces it for anything that wants the old shape.

Because the automaton reports **every** token spanning a position, contested-token resolution is applied when the token index is built rather than per match — one token maps to at most one gene by construction.

### Stage 3: False Positive Filtering

After Stage 2 finds a match, four false positive filters are applied to eliminate problematic patterns:

**Filter 1: Single Letter Aliases.** Any matched alias that is a single uppercase letter (A-Z) is rejected. Many genes have single-letter aliases that are far too ambiguous for text matching.

- **Example:** PPIB has alias "B". Without this filter, every occurrence of the letter "B" bounded by punctuation would match. With the filter, PPIB alias "B" is blocked entirely.

**Filter 2: Roman Numerals.** Matched aliases that are Roman numerals (composed entirely of I, V, X) are rejected. Scientific text frequently uses Roman numerals for numbering.

- **Example:** GCNT2 has alias "II". Without this filter, text like "Complex II" or "(I-V)" would falsely match GCNT2. The Roman numeral filter blocks "II" as a Roman numeral pattern. In production, this eliminated 108 false GCNT2 occurrences.

**Filter 3: Domain Abbreviations.** A small stoplist of tokens that HGNC lists as gene names but which, in AOP-Wiki prose, never denote the gene: `ROS` (an alias of ROS1, but always "reactive oxygen species" here), `ECM` (an alias of MMRN1, always "extracellular matrix"), and `spatial` (an alias of TBATA, and an ordinary English adjective). Each was verified against the corpus before being added.

Stoplisting an alias does not cost the gene its real mentions — `ROS1` itself still matches normally.

**Filter 4: Short Tokens Need Gene Context.** Tokens of 3 characters or fewer are only accepted when the surrounding ±50 characters contain a cue that the prose is about genes or proteins — `gene`, `expression`, `mRNA`, `transcript`, `protein`, `receptor`, `encoded`, and similar.

Cues are matched on **word boundaries**, not as substrings. As substrings, "generation of reactive oxygen species" would satisfy the `gene` cue, which is exactly the context the filter exists to reject.

This replaced an earlier rule that rejected short tokens only when a bracket appeared anywhere in the context window. That made the verdict depend on unrelated punctuation: `TH` survived on 56 entities purely because no bracket happened to fall nearby.

**Filter 5: Gene-Specific Context Rules.** Targeted rules for known problematic patterns:

- **IV gene:** When matched alias "IV" appears near "Complex I" or "(I-V)" numbering patterns, the match is rejected.
- **II alias (GCNT2):** When "II" appears near "(I-V)" numbering or "complexes" text, the match is rejected.

### Contested tokens

Filtering alone cannot fix a token that several genes legitimately claim. Because the matcher tests each gene independently, `AR` — the approved symbol of AR, and a previous symbol of both FDXR and AREG — caused all three genes to be asserted together on 29 entities, where at most one can be correct.

`build_token_owners` inverts the dictionary to find every token claimed by more than one gene, and awards each to the gene whose **approved symbol** it is, which is the reading a curator would take. A contested token that is nobody's approved symbol is retired for every gene, since no reading is defensible.

Two design notes:

- Genuinely ambiguous tokens such as `AR`, `TH`, `ER` and `T4` are deliberately **not** stoplisted. They are ambiguous rather than always-wrong, so they pass through ownership resolution and the context rule, which can still admit them where the text supports it.
- HGNC columns 6–7 (accession numbers, Ensembl ID) are **not** loaded as gene names. They are database identifiers, not names any Key Event description would use, and they are shared across genes — `AF250841` alone was claimed by 71 of them.

### Proven Results

The 2025 filtering work achieved a **14.6% reduction** in false positive gene mappings (1,398 gene occurrences eliminated):

| Gene | Alias | Before Filtering | After Filtering | Reduction |
|------|-------|-----------------|-----------------|-----------|
| GCNT2 | "II" | 108 | 0 | 100% |
| PPIB | "B" | 134 | 4 | 97% |
| IV | "IV" | 37 | 4 | 89% |

The later ownership and abbreviation work targeted a different class of error, measured in published RDF:

| Token | Claimed by | Entities affected | Reading in AOP text |
|-------|-----------|-------------------|---------------------|
| `ROS` | ROS1 | 136 | reactive oxygen species |
| `TH` | TH | 56 | thyroid hormone |
| `spatial` | TBATA | 40 | ordinary English adjective |
| `ECM` | MMRN1 | 37 | extracellular matrix |
| `AR` | AR + FDXR + AREG | 29 (all three at once) | androgen receptor |

Measured over the full KE/KER corpus (2,737 texts, `aop-wiki-xml-2026-06-18`), comparing the matcher before and after:

| | before | after | change |
|---|---:|---:|---:|
| gene associations | 6,710 | 3,927 | −41.5 % |
| distinct genes | 1,516 | 1,035 | −31.7 % |
| dictionary tokens | 212,378 | 150,674 | −29.1 % |
| match variants held in memory | 10,406,522 | 7,383,026 | −29.1 % |
| matcher runtime | 691 s | 505 s | −26.9 % |

Spot-checking the largest removals against HGNC confirms each was driven by a short alias meaning something else entirely in toxicology prose:

| Gene | Matched via | What the token means here |
|------|------------|---------------------------|
| ROS1 | `ROS` | reactive oxygen species |
| ITK, SLC22A3 | `EMT` | epithelial–mesenchymal transition |
| DLAT, SNORA62, CST12P | `E2` | estradiol |
| IRF6 | `LPS` | lipopolysaccharide |
| AKR1B1, FDXR, AREG | `AR` | androgen receptor (which keeps the token) |
| THPO | `TPO` | thyroid peroxidase (which keeps the token) |
| MMRN1 | `ECM` | extracellular matrix |

Genes written by their approved symbol are unaffected: AHR holds at 36 occurrences, TPO at 35, AR at 55, SHH at 34.

Because BERN2 output is unioned in, the published drop is smaller than the regex drop: of the 2,812 regex associations removed, 1,507 are for genes BERN2 finds independently.

### Recall gap at text boundaries (fixed)

Every `genedict2` variant had the form delimiter + token + delimiter, so a token that **opened** a text had no leading delimiter to match against and was missed entirely, however unambiguous it was. The automaton treats the text edges as boundaries, closing this.

Measured effect on the full corpus: 3,927 → 4,057 gene associations (+3.3%) and 1,035 → 1,046 distinct genes. Two genes lost a match, both correctly — `NPAT` was matching on `E14` (embryonic day 14) and `H2AC20` on `H2A` (the histone family, not that specific gene).

The context window used by the short-token filter is also snapped outward to whole words. A fixed character window could sever a cue and flip the verdict on a single character: one observed match had `over-expression` truncated to `over-expressio`, admitting `STZ` (streptozotocin) as the gene `ST3GAL4`.

## BERN2 NER+EL Gene Enrichment

The regex algorithm can only match text that uses a canonical HGNC symbol
or a known alias. It misses genes named descriptively -- *"nicotinic
acetylcholine receptor"*, *"protein kinase B"*, *"calmodulin"* -- which
AOP-Wiki authors use heavily in Key Event descriptions. **BERN2**
(DMIS-Lab), a Named Entity Recognition + Entity Linking model, closes
that gap: it recognises descriptive gene mentions and normalises them to
NCBI Gene IDs in one pass.

This enrichment is opt-in via `PipelineConfig.enable_bern2` (default
`False`). The weekly `rdfgeneration.yml` workflow enables it with the
`--enable-bern2` flag on `run_conversion.py`.

### How it works

1. For each Key Event description, the text is sent to the BERN2 hosted
   API (`http://bern2.korea.ac.kr/plain`).
2. BERN2 returns gene entities annotated with NCBI Gene IDs.
3. NCBI Gene -> HGNC is resolved via the BridgeDb batch API (system
   code `L`), the same service the chemical and regex-gene mappers use.
4. The resulting HGNC IDs are unioned with the regex mapper's output.

Scope is **KE descriptions only** -- Key Event Relationships stay
regex-only. BERN2's per-method evidence and a feasibility comparison
against the regex baseline are in `prototypes/ner_el_spike/REPORT.md`
(95.98% of detected genes normalise to HGNC; +232 HGNC IDs over regex
on a 100-KE sample).

### Provenance predicates

When enrichment is active, `AOPWikiRDF-Genes.ttl` records which method
found each gene. `edam:data_1025` stays the **union** of both methods
(so existing queries are unaffected); two extra predicates carry the
per-method subsets:

```turtle
aop.events:888
    edam:data_1025        hgnc:A, hgnc:B, hgnc:C ;
    :geneDetectedByRegex  hgnc:A, hgnc:B ;
    :geneDetectedByNER    hgnc:B, hgnc:C .
```

A consumer wanting a regex-only view queries `:geneDetectedByRegex`; a
high-confidence (both-methods) view intersects the two predicates. An
empty subset omits its predicate -- KERs never carry `:geneDetectedByNER`.

### Response cache and the cold start

Every BERN2 and BridgeDb response is cached on disk under
`data/cache/bern2/`, keyed by the SHA of its input text. The weekly run
therefore only hits the network for KE descriptions that *changed* since
the previous run -- typically a handful.

Before enabling the flag in production, the cache must be warmed for the
full corpus (the **cold start**):

```bash
python scripts/warm_bern2_cache.py --xml data/aop-wiki-xml-YYYY-MM-DD
```

The cold start is resumable -- re-running it skips everything already
cached, so it is safe to interrupt. The BERN2 hosted API emits bare
`NaN` for the `prob` field of neural-normalised entities (not valid
JSON); the client parses responses with an explicit `parse_constant`
handler so this does not break decoding.

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

When BERN2 enrichment is active (see *BERN2 NER+EL Gene Enrichment* above), each KE/KER block additionally carries `:geneDetectedByRegex` and `:geneDetectedByNER` provenance predicates; `edam:data_1025` remains the union of both methods.

### AOPWikiRDF-Enriched.ttl

The enriched file contains only `owl:sameAs` cross-reference triples linking chemicals and biological objects to external database identifiers. It does not duplicate entity type declarations or base properties.

### AOPWikiRDF-Void.ttl

The VoID metadata file describes the parent dataset (`:AOPWikiRDF`) with `void:subset` links to the three content files, plus linkset descriptions for HGNC gene data and Protein Ontology mappings. Each subset includes provenance information (creation date, source files, BridgeDb URL) and triple counts.
