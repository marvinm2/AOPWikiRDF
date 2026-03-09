# BioBERT NER Feasibility Report

## Executive Summary

BioBERT NER (alvaroalon2/biobert_genetic_ner) and the current HGNC regex-based gene mapper operate at fundamentally different abstraction levels: BioBERT recognizes descriptive protein/gene name spans in natural language (e.g., "NADH-UBIQUINONE OXIDOREDUCTASE", "PEROXISOME PROLIFERATOR-ACTIVATED RECEPTOR"), while the regex approach matches standardized HGNC gene symbols (e.g., MT-ND1, PPARA, CYP19A1). With only 5% overlap across 100 Key Event descriptions, the two methods are complementary rather than competitive. **Recommendation: Do not integrate BioBERT into the production pipeline.** The methods answer different questions, and the cost of integration outweighs the benefit given the project's goal of mapping KE descriptions to HGNC-identifiable genes for RDF enrichment.

## Methodology

### Evaluation Setup

- **Sample size:** 100 Key Event descriptions selected from data/AOPWikiRDF.ttl via SPARQL query
- **Selection criteria:** Descriptions longer than 50 characters, covering molecular, cellular, organ, and organism-level KEs
- **BioBERT model:** `alvaroalon2/biobert_genetic_ner` via HuggingFace transformers pipeline with `aggregation_strategy="simple"` and confidence threshold > 0.5
- **Regex baseline:** Current production three-stage algorithm (screening with genedict1, precision matching with genedict2, false positive filtering)
- **Input truncation:** 512 characters for BioBERT model input

### Comparison Framework

For each KE description, both methods were run independently. Results were categorized as:
- **Both:** Genes found by both methods
- **BioBERT-only:** Entities found exclusively by BioBERT
- **Regex-only:** Genes found exclusively by the regex approach

No manual ground truth annotation was performed; metrics use each method's output as a reference point for comparison rather than absolute precision/recall.

## Results

### Aggregate Statistics

| Metric | BioBERT NER | Regex (HGNC) |
|--------|------------|--------------|
| Total entities found | 213 | 258 |
| Unique to method | 200 | 245 |
| Shared (overlap) | 13 | 13 |
| KEs with disagreements | 72 / 100 | 72 / 100 |

### Cross-Method Comparison (BioBERT vs Regex as Baseline)

| Metric | Value |
|--------|-------|
| Precision (BioBERT vs regex baseline) | 6.1% |
| Recall (BioBERT vs regex baseline) | 5.0% |
| F1 (BioBERT vs regex baseline) | 5.5% |
| Agreement rate | 28% |
| Overlap (shared entities) | 13 / 458 total unique = 2.8% |

These low cross-method metrics confirm the two approaches are measuring different things, not that one is "worse" than the other.

### Runtime Comparison

| Metric | BioBERT | Regex |
|--------|---------|-------|
| Total time (100 KEs) | 12.08 s | 21.86 s |
| Per KE description | 0.121 s | 0.219 s |
| Model loading overhead | Included in total | N/A |
| Dictionary build time | N/A | Not included |

BioBERT is 1.8x faster per KE, though the regex timing does not include the one-time cost of building the HGNC gene dictionary from BridgeDb API calls (~30-60 seconds).

## Error Analysis

### What BioBERT Catches That Regex Misses

BioBERT excels at recognizing descriptive protein and receptor names in natural language text. Examples from the prototype:

1. **Full protein names:** "NADH-UBIQUINONE OXIDOREDUCTASE" (KE 888), "ACETYLCHOLINESTERASE" (KE 12), "THYROPEROXIDASE" (KE 279)
2. **Receptor families:** "GABAA RECEPTOR" (KE 667), "NICOTINIC ACETYLCHOLINE RECEPTOR" (KE 559), "VASCULAR ENDOTHELIAL GROWTH FACTOR RECEPTORS" (KE 305)
3. **Protein family members:** "ERBB1/2/3/4", "HER1/2/3/4" (KE 941), "SRC FAMILY KINASES" (KE 1884)
4. **Enzyme descriptions:** "CYTOCHROME P450 AROMATASE" (KE 36), "HISTONE DEACETYLASES" (KE 1502), "CHITIN SYNTHASE" (KE 1522)

These are genuinely useful biological entity mentions that the regex approach cannot detect because they are not HGNC gene symbols.

### What Regex Catches That BioBERT Misses

The regex approach excels at matching standardized HGNC gene symbols, including aliases and synonyms. Examples:

1. **Mitochondrial genes:** MT-ND1, MT-ND2, MT-ND3, MT-ND4, MT-ND4L, MT-ND5, MT-ND6 (KE 888)
2. **Specific gene symbols:** GRIN1, GRIN2A, GRIN2B, GRIN2C, GRIN2D (KE 201, 875), FKBP1B, FKBP2, FKBP5 (KE 980)
3. **Signaling pathway genes:** AKT1, PIK3CA, PTPN1 (KE 941), MAP3K7, MYD88, TRAF6 (KE 1700)
4. **Cancer-related genes:** TP53, BRAF, CDK4, RB1, STK11, CHEK2 (KE 1193)

BioBERT fails to detect these because they appear as short symbol abbreviations in text, not as descriptive protein/gene names that the NER model was trained on.

### False Positives Unique to Each Method

**BioBERT false positives:**
- HTML entity artifacts: "&ALPHA;", "&BETA;", "&NBSP", "&NDASH" fragments appear as entity spans (KE 718, 998, 1710)
- Non-gene concepts tagged as genes: "HUMAN" (KE 888), "FISH" (KE 36), "TRANSCRIPTION" (KE 228)
- Truncated entity spans: "OPROPENYLPYRROLID" (KE 201), "YROSINE KINASE DOMAIN" (KE 941), "BRIN STRANDS" (KE 1866)
- Chemical/EC number artifacts: "KEGG ID E.C. 1.14.99.1" (KE 79), "2-CARBOXY-3-CARBOXYMETHYL-4-" (KE 201)

**Regex false positives (likely):**
- Short ambiguous symbols matching gene aliases: TBATA (KE 402, 1686), HYCC1 (KE 378, 1395), ARCN1 (KE 1250)
- Genes matching abbreviations in clinical context: ACD (KE 827), SPI1 (KE 459), CP (KE 459)
- Known false positive patterns (partially filtered): IVNS1ABP (KE 888), FMN1 (KE 888)

### Categories of Disagreements

Analysis of the 72 disagreement cases reveals four dominant patterns:

1. **Different abstraction levels (most common):** BioBERT finds "CALCINEURIN" while regex finds FKBP1B, FKBP5, PPIB -- the same biological pathway described at protein-name vs gene-symbol level (KE 980)
2. **BioBERT finds receptors, regex finds subunits:** BioBERT tags "NMDA RECEPTORS" while regex matches individual subunit genes GRIN1, GRIN2A-D (KE 201, 875)
3. **Only regex has matches:** For many KEs describing organ/organism-level effects (body weight, lung function, depression), BioBERT finds no gene entities while regex matches incidental gene symbols in the text (KE 864, 1250, 1346)
4. **Only BioBERT has matches:** For KEs focused on specific receptors or enzymes, BioBERT tags the protein name while regex has no HGNC symbol match (KE 667, 559, 867)

## Feasibility Assessment

### Can BioBERT Replace the Regex Approach?

**No.** The methods have fundamentally different outputs:
- BioBERT produces descriptive text spans (protein names, receptor families)
- Regex produces standardized HGNC gene symbols with identifiers

The pipeline requires HGNC identifiers to generate RDF triples with `identifiers.org/hgnc/` URIs and BridgeDb cross-references. BioBERT output cannot be directly used for this purpose without an additional normalization step to map descriptive names back to HGNC IDs -- a non-trivial entity linking problem.

### Can BioBERT Complement the Regex Approach?

**In theory, yes, but the integration cost is high.** A complementary approach would:
1. Run BioBERT NER to find descriptive protein/gene mentions
2. Normalize BioBERT entities to HGNC symbols (requires a protein-name-to-gene-symbol mapping database)
3. Merge with regex results, deduplicating

This could capture genes mentioned by descriptive name only (e.g., "thyroperoxidase" -> TPO, "aromatase" -> CYP19A1). However, step 2 is itself a significant research problem with no off-the-shelf solution for the AOP-Wiki domain.

### Integration Requirements

If integration were pursued:
- **New dependencies:** transformers (>=4.0), torch (>=2.0) -- adds ~2GB to the environment
- **Model download:** ~440MB BioBERT model on first run
- **CI impact:** GPU not required but inference adds ~12 seconds to pipeline runtime
- **Entity normalization:** Would need a descriptive-name-to-HGNC lookup (does not exist as a library)
- **Maintenance burden:** Model updates, tokenizer compatibility, entity normalization dictionary

### Cost-Benefit Analysis

| Factor | Assessment |
|--------|-----------|
| Accuracy improvement | Marginal for HGNC gene mapping; BioBERT finds different entities |
| New capabilities | Could identify protein families and receptors not in HGNC |
| Dependency weight | +2GB (torch + transformers) vs current ~50MB environment |
| Maintenance cost | High -- model versioning, normalization dictionary updates |
| CI pipeline impact | +12s inference + model caching complexity |
| Entity normalization | Unsolved problem -- no standard tool maps free-text protein names to HGNC |

## Recommendation

**Do not integrate BioBERT into the production pipeline.**

### Reasoning

1. **Misaligned outputs:** The pipeline needs HGNC gene symbols to produce identifiers.org URIs. BioBERT produces descriptive text spans that require an additional unsolved normalization step.

2. **Minimal overlap (5%):** The two methods find almost entirely different things. This is not a precision/recall gap to close -- it is a fundamental difference in what is being detected.

3. **Dependency burden disproportionate to benefit:** Adding ~2GB of ML dependencies and model management complexity for marginal gene coverage improvement is not justified.

4. **Current approach is effective:** The three-stage regex system with precision filtering already achieves strong results for its intended purpose (HGNC symbol detection with 14.6% false positive reduction).

### What Would Need to Change

BioBERT integration would become viable if:

1. **A reliable protein-name-to-HGNC normalization tool existed** -- this is the primary blocker. Tools like BioPortal or UniProt's ID mapping API could serve as starting points, but no turnkey solution handles the variety of descriptive names BioBERT produces.

2. **The RDF schema expanded to include non-HGNC biological entities** -- if the project wanted to annotate KEs with protein family mentions, receptor types, or enzyme classes beyond what HGNC covers, BioBERT would be the right tool.

3. **A lightweight NER model emerged** -- the current torch/transformers stack is heavy. A distilled model or rule-based approach trained on biomedical text could reduce the integration cost.

### Prototype Preservation

The prototype is preserved in `prototypes/biobert_ner/` for future reference. If any of the above conditions change, the comparison framework and results provide a baseline for renewed evaluation.

---

*Report generated from prototype results on 100 KE descriptions.*
*Model: alvaroalon2/biobert_genetic_ner*
*Comparison date: March 2026*
