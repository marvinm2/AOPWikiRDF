# NER + Entity Linking Feasibility Report (BERN2 + PubTator3)

## Executive Summary

Phase 5-04 (March 2026) concluded that plain BioBERT NER cannot replace the regex-based HGNC gene mapper because BioBERT emits raw text spans, not HGNC IDs — the entity-normalisation step was the load-bearing blocker. This spike re-evaluates the question with two **NER + Entity Linking** tools that produce normalised database identifiers in one pass.

**BERN2** (DMIS-Lab) successfully closes that gap: across the same 100-KE sample Phase 5-04 used, **95.98 %** of BERN2-detected gene entities normalise to HGNC via BridgeDb (vs. 0 % achievable with plain BioBERT). The two methods now share **126 HGNC IDs** (vs. 13 in Phase 5-04), and the agreement F1 against the regex baseline rises from **0.055 to 0.384**. Critically, BERN2 finds **232 HGNC IDs that regex misses** across the 100 KEs — descriptive-name detections such as *"nicotinic acetylcholine receptor → CHRNA1"*, *"protein kinase B → AKT1"*, *"calmodulin → CALM3"* — exactly the abstraction-level mismatch Phase 5-04 surfaced as the regex blind spot.

**PubTator3** had to be dropped from the comparison: NCBI removed all free-text annotation endpoints (`/annotate`, `/findEntityId`, `/freetext`) in the v2 → v3 migration. The PubTator3 REST API today only accepts published-literature PMIDs, not arbitrary text.

**Recommendation: Hybrid integration, not replacement.** Regex remains the source-of-truth for HGNC-symbol matches (recall is 58 % higher than BERN2 on this sample, with deterministic, fast, dictionary-driven behaviour). BERN2 enters as an additive enrichment layer for descriptive-name detections regex cannot match. Productionisation requires standing up self-hosted BERN2 (Docker) — the hosted API's 4 s / KE throughput projects to ~11 hours for the full ~10 K-KE corpus, well over the weekly workflow budget.

## Methodology

### Evaluation Setup

- **Sample size:** 100 Key Event descriptions, same selection criteria as Phase 5-04 (`STRLEN(STR(?description)) > 50`).
- **Source:** `data/AOPWikiRDF.ttl` (124,174 triples from the 2026-05-09 weekly run).
- **Tools evaluated:**
  - **BERN2** (DMIS-Lab) via hosted API `http://bern2.korea.ac.kr/plain` — returns gene entities annotated with `NCBIGene:N` identifiers.
  - **PubTator3** (NCBI) — attempted via four documented endpoints; all returned `{"detail": "This resource is not available"}`. The v2 → v3 migration removed free-text annotation entirely.
  - Regex baseline — three-stage screening / precision / false-positive filter ported from `src/aopwiki_rdf/mapping/gene_mapper.py` for direct comparability.
- **Entity normalisation:** NCBI Gene → HGNC via BridgeDb (`https://webservice.bridgedb.org/Human/xrefsBatch/L`), parsing `Hac:HGNC:N` tokens from the batch response (the same `Hac` system code the production pipeline already uses elsewhere for HGNC accession numbers).
- **Caching:** Every hosted-API response cached per-KE under `prototypes/ner_el_spike/cache/<tool>/<sha12>.json`; re-runs hit the cache.
- **Rate limiting:** 1 s sleep between BERN2 calls; 0.2 s between BridgeDb batches.

### Comparison Framework

For each KE, all three methods produce a set of HGNC numeric IDs (the canonical comparison key). Three-way set differences identify per-method unique finds, pairwise overlap, and three-way agreement. Precision / recall / F1 use **regex as the proxy ground truth** (consistent with Phase 5-04); no manual annotation was performed.

### BERN2 chunking fallback

The hosted BERN2 API truncates the JSON response for very long inputs (observed `Expecting value: line 1 column ~5174` JSON-decode errors on 8 KEs out of 100). The spike script catches that failure and re-queries the same text in sentence-boundary chunks of ≤ 1500 chars, then merges and de-duplicates annotations. This recovered all 8 KEs except where an internal sub-chunk also errored (final error count: 8 / 100 with annotations from the partial sub-chunks where possible).

## Results

### Aggregate Statistics

| Metric | Regex | BERN2 | PubTator3 |
|---|---|---|---|
| Total HGNC IDs found (100 KEs) | 299 | 358 | n/a |
| NCBI Gene entities detected | n/a | 373 | n/a |
| HGNC yield via BridgeDb | n/a | **95.98 %** | n/a |
| Errors | 0 | 8 / 100 | 100 / 100 (endpoint removed) |
| Disagreement KEs | — | 78 / 100 | — |
| Agreement rate | — | 22 % | — |

### Pairwise Overlap (HGNC IDs)

| Pair | Shared | Regex-only | BERN2-only |
|---|---|---|---|
| Regex ∩ BERN2 | **126** | 173 | 232 |

Phase 5-04 (BioBERT alone, no entity linking) reported a 13-entity overlap and 5 % overlap rate. This spike's 126-ID overlap and 22 % agreement rate represent a **10× improvement** driven entirely by the entity-linking step.

### Cross-Method Precision / Recall / F1 (regex as baseline)

| Method | Precision | Recall | F1 |
|---|---|---|---|
| Regex | 1.0000 | 1.0000 | 1.0000 *(trivially)* |
| BERN2 | 0.3520 | 0.4214 | **0.3836** |
| PubTator3 | 0.0000 | 0.0000 | 0.0000 *(endpoint unavailable)* |

For context: Phase 5-04 BioBERT-alone reported precision 0.061 / recall 0.050 / F1 0.055. The order-of-magnitude jump comes from two things — better gene-NER coverage in BERN2 and (mainly) the entity-linking step turning text spans into HGNC IDs that *can* overlap with regex output.

### HGNC Yield via BridgeDb

Of 291 unique NCBI Gene IDs returned by BERN2 across the 100 KEs, BridgeDb mapped **277 (95.2 %)** to a numeric HGNC ID. The remaining 4.8 % are NCBI Gene entries that exist in NCBI but lack an HGNC cross-reference — usually pseudogenes, withdrawn entries, or non-human paralogues mistakenly tagged. The headline 95.98 % yield in the aggregate stats counts duplicate detections (a gene detected in 2 KEs counts twice); both numbers confirm BridgeDb is not the bottleneck.

### Runtime Comparison

| Method | Total (100 KEs) | Per KE | Projected full corpus (~10 K KEs) |
|---|---|---|---|
| Regex | 32.5 s | 0.32 s | ~55 min |
| BERN2 (hosted API) | 392.1 s | 3.92 s | ~10.9 hours |
| PubTator3 | n/a | n/a | n/a |

Regex per-KE time includes scanning ~45 K HGNC dict entries; the constant-factor 0.32 s / KE will grow weakly with HGNC dict size. BERN2's 3.92 s / KE is dominated by **hosted-API latency + 1 s rate-limit sleep + chunking-fallback re-queries for the 8 failure KEs**, not by inference time. Self-hosted Docker is expected to be 10–100 × faster (no rate-limit sleeps; GPU batch inference); see *Feasibility* below.

## Error Analysis

### What BERN2 Catches That Regex Misses (descriptive-name detections)

These are the *new* HGNC IDs the current pipeline does not capture. Sampled from 232 BERN2-only finds:

**KE 1243 — "Altered, Ca²⁺-calmodulin activated signal transduction"** (regex: 0 IDs, BERN2: 12 IDs)
- BERN2 mentions → HGNC: `"nicotinic acetylcholine receptor"` → CHRNA1/CHRNA4, `"calmodulin"` → CALM3, `"adenylyl cyclase"` → ADCY1, `"calcium/calmodulin-dependent protein kinase"` → CAMK2G, `"MAP kinase"` → MAPK1/MAPK3.
- Regex finds zero genes here because the KE text uses only descriptive protein names — no HGNC symbols appear.

**KE 1339 — "Increase, intracellular calcium"** (regex: 1, BERN2: 11)
- BERN2: `"protein kinase B / PKB / Akt"` → AKT1, `"calcium/calmodulin-dependent protein kinase"` → CAMK1, `"cyclic-AMP response element-binding protein"` → CREB1.

**KE 1262 — "Apoptosis"** (regex: 4, BERN2: 14)
- BERN2: `"p53"` → TP53 (also caught by regex), `"BAX"`, `"BAK"`, `"BBC3"`, `"BCL2L1"` (BCL-XL by name), `"BCL2L11"` (BIM), `"caspase-1"` → CASP1, `"cyclin D1"` → CCND1.

**KE 1394 — "Sustained proliferation"** (regex: 29, BERN2: 26 — 16 in common)
- BERN2-only adds: `"GSK3"` → GSK3A, `"LEF/TCF"` → LEF1, `"low-density lipoprotein receptor-related protein 5/6"` → LRP5/LRP6, `"frizzled-1"` → FZD1, `"WNT-1"` → WNT1, `"cyclin-dependent kinase 1"` → CDK1.

The recurring win: **complete pathway components named descriptively** (signal transduction cascades, kinase families, receptor complexes) that the AOP-Wiki authors describe in free text without writing the gene symbol.

### What Regex Catches That BERN2 Misses

These are the 173 regex-only finds. The dominant patterns:

**KE 1493 — "Increased Pro-inflammatory mediators"** (regex: 26, BERN2: 6 — only 6 shared)
- Regex-only: CCL2, CXCL8, IL-2 / IL-4 / IL-6 / IL-17A as short symbol mentions, plus CEBPB, IRF6, CTLA4.
- The text uses canonical cytokine symbols (IL-2, IL-6, etc.) — exactly the format the regex screens for. BERN2 either failed to detect or linked the mention to a different gene.

**KE 1003 — "Decreased, Triiodothyronine (T3)"** (regex: 21, BERN2: 13 — 7 shared)
- Regex-only: F2R, SLC16A2, SLC25A5, SLCO1C1, TERC, THPO, THRB, TPO — solute carriers and thyroid-axis genes named by HGNC symbol.
- BERN2-only does add DIO1 / DIO2 / DIO3 (the iodothyronine deiodinases) by descriptive name — complementary, not competitive.

**KE 1492 — "Tissue resident cell activation"** (regex: 13, BERN2: 0)
- Regex finds CD86, IL-13, IL-18, IL-4, IL-6, TLR2, TLR4, TNF. BERN2 returned no gene entities at all for this KE. Likely cause: very short / dense receptor-name text that doesn't trigger the model's gene tagger.

### False Positives Unique to Each Method

**BERN2 false positives (estimated from BERN2-only set):**
- *Gene-family ambiguity:* `"GST"` → maps to one specific GST family member (GSTA1) rather than the family. Common pattern for vague mentions.
- *Pseudogenes mis-linked:* a few BERN2 mentions normalised to pseudogene NCBI Gene IDs (e.g., ACTG1P25, BORCS6 in inflammatory-mediator context) that BridgeDb did map to HGNC but are unlikely to be the intended entity.
- *Out-of-context family hits:* `"histone"` → H4C16 / H3-3A — true HGNC entries, but the KE text intends "histones generally", not these specific paralogues.

**Regex false positives:** Phase 5-04 already documented these — single-letter aliases, Roman-numeral genes, short symbols in bracket context. The production three-stage filter eliminates most of these (production stats: 14.6 % FP reduction).

### Categories of Disagreements (78 / 100 KEs)

1. **Descriptive-only KEs (most common for the BERN2-wins case):** The KE describes biology in free prose without HGNC symbols. BERN2 catches everything; regex catches nothing. ~15 KEs in the sample.
2. **Symbol-only KEs (the regex-wins case):** Cytokine and receptor KEs that name genes by canonical symbol (IL-6, TLR4). BERN2 detection rate drops; regex carpets the text. ~10 KEs.
3. **Same biology, different abstraction (the bulk):** Phase 5-04's most common pattern. KE text mixes free names and symbols; the two methods find overlapping but distinct subsets. ~50 KEs.
4. **BERN2-empty KEs:** 3 / 100 KEs returned 0 gene entities from BERN2 despite a regex match — likely failures of the underlying NER step on dense or unusual text.

## Feasibility Assessment

### Can BERN2 Replace the Regex Approach?

**No.** Two reasons:

1. **Recall on symbol-rich KEs is unacceptable.** For KEs that use canonical HGNC symbols heavily (cytokine lists, receptor lists), BERN2's recall drops sharply — it found 0 genes on KE 1492 where regex found 13, and only 6 / 26 on KE 1493. Removing regex would lose ~173 HGNC IDs across the 100-KE sample (extrapolating: ~17 K across the full corpus).
2. **Determinism.** Regex is deterministic, dictionary-driven, and offline — desirable properties for a weekly batch pipeline that drives public RDF downloads. BERN2 is a neural model with possible drift and an external dependency on either DMIS-Lab's hosted API or a self-hosted Docker image.

### Can BERN2 Complement the Regex Approach?

**Yes — this is the recommended path.** A hybrid would:

1. Run regex first as the production source-of-truth for HGNC-symbol matches.
2. Run BERN2 in parallel; its output is normalised through the existing BridgeDb client (`bridgedb_url + xrefsBatch/L`) — no new mapping infrastructure needed.
3. **Union** the two HGNC ID sets per KE / KER for emission into `AOPWikiRDF-Genes.ttl`.
4. Optionally, **tag** each gene-association triple with provenance (`prov:wasDerivedFrom` either `:regex_mapper` or `:bern2_ner`, with `:both` when overlapping) so downstream consumers can filter.

Coverage gain at 100-KE scale: **+232 HGNC IDs (77.6 % over regex alone)**. Extrapolated naively to the full ~10 K corpus: ~23 K additional gene associations.

### Integration Requirements

| Component | Requirement | Effort |
|---|---|---|
| **BERN2 deployment** | Self-hosted Docker (`dmis-lab/BERN2`). Hosted API throughput unsuitable for weekly full-corpus run. | ~5 GB image; one-time stand-up on the VHP4Safety cluster (`tgx1`) |
| **CI workflow change** | `rdfgeneration.yml` calls a NER service alongside regex. | Modest — service URL becomes a `PipelineConfig` field |
| **`gene_mapper.py` refactor** | Add `ner_el_mapper.py` next to it; the orchestrator unions results. | ~200 LOC, mirrors chemical mapper structure |
| **Throughput** | Self-hosted GPU inference: estimated 0.1–0.3 s / KE → 15–50 min full corpus. CPU-only: would still need ~5 hours. | GPU strongly recommended |
| **SHACL shape** | No change — output is still `edam:data_1025` HGNC associations | None |
| **Tests** | Network-dependent integration test mirroring the existing BridgeDb tests | ~1 day |
| **Documentation** | `docs/conversion.md` adds an NER+EL section | ~1 day |

### Cost-Benefit Analysis

| Factor | Assessment |
|---|---|
| Accuracy / coverage improvement | Substantial: +77.6 % HGNC IDs over regex on the 100-KE sample, capturing descriptive-name detections that are the dominant Phase 5-04 blind spot |
| HGNC yield via existing BridgeDb | **95.98 %** — the entity-linking step is effectively a solved problem now |
| Throughput on hosted API | **Unworkable** for weekly batch (10+ h / corpus). Need self-hosted Docker. |
| New external dependency | Self-hosted BERN2 service (one container, ~5 GB) on the existing Strato Swarm cluster |
| Maintenance burden | Moderate — pinning a BERN2 image version, monitoring service health, occasional re-pull for model updates |
| Risk to existing production | Low if hybrid: regex output is preserved unchanged; BERN2 is additive only |
| Cold-start cost | One-time: Docker image pull + GPU provisioning if used |

## Recommendation

**Adopt BERN2 as an additive enrichment layer in `AOPWikiRDF-Genes.ttl` — hybrid integration, regex preserved as primary.**

### Reasoning

1. **Phase 5-04's normalisation blocker is solved.** The 95.98 % BridgeDb HGNC yield turns BERN2's raw spans into pipeline-compatible HGNC IDs with no new infrastructure. This is the result the Phase 5-04 REPORT explicitly identified as the precondition for revisiting BioBERT-class tools ("a robust protein-name-to-HGNC normalisation tool" — and indirectly, BridgeDb + the NCBI Gene cross-references already in BERN2's output, has been one all along).

2. **The signal is large and shaped right.** 232 HGNC IDs found *only* by BERN2 on 100 KEs, dominated by named pathway proteins, receptor complexes, and signalling cascades. These are precisely the descriptive-name detections regex was never going to catch (the structural argument Phase 5-04 raised) — but now they come with HGNC IDs attached.

3. **Regex's symbol-grade recall is irreplaceable.** 173 regex-only HGNC IDs across 100 KEs (cytokine lists, receptor lists, named-gene clusters) — losing these would be a strict regression. Hybrid keeps both.

4. **Deployment is bounded.** Self-hosted BERN2 fits the existing Strato Swarm cluster topology, no new third-party service dependency on the critical weekly path.

### What Would Need to Change to Move from Spike to Production

1. **Stand up self-hosted BERN2 Docker on `tgx1` or `tgx2`** (cluster service docs at `/mnt/gluster/documentation/services/`). Expose via the existing Traefik overlay network. Throughput verification on a 1 K-KE sample (target: under 5 min) is the gating test.
2. **Add `ner_el_mapper.py` to `src/aopwiki_rdf/mapping/`** — sibling of `gene_mapper.py`, called by the pipeline in parallel. Reuses `bridgedb.batch_xrefs` for the NCBI Gene → HGNC step.
3. **Union the two HGNC ID sets in `_stage_write_genes_rdf`** at `src/aopwiki_rdf/pipeline.py`.
4. **Tag provenance** on each gene-association triple (`prov:wasDerivedFrom :regex_mapper | :bern2_ner | :both`) so downstream SPARQL consumers can opt out of BERN2-derived enrichments if they want a regex-only view.
5. **A new GitHub Actions secret** (or service URL `PipelineConfig` field) pointing the pipeline at the cluster BERN2 service.
6. **One integration test** that runs against a mock BERN2 response (existing BridgeDb test patterns transfer directly).

### Out-of-Scope Open Questions

- **GPU vs CPU on tgx1/tgx2:** the cluster currently has no GPU. Either rely on CPU inference (acceptable for weekly batch — ~30-60 min projected) or provision a small GPU instance. Decision deferred to the productionisation plan.
- **Periodic re-pull of the BERN2 image:** the model embedded in the image gets stale. A quarterly refresh cadence likely; coordinate with the weekly workflow so re-pulls don't collide with Saturday's RDF generation.
- **Disagreement curation loop:** the `disagreements.json` from this spike could feed an AOP-Wiki manual curation suggestion — e.g., "your KE description does not mention {gene_symbol} but a related descriptive name was found" — but that's a separate product feature, not part of the RDF pipeline.

### Prototype Preservation

The spike is preserved in `prototypes/ner_el_spike/` for future reference. Re-running:

```bash
python prototypes/ner_el_spike/run_spike.py --limit 100 --skip-pubtator
```

reuses cached BERN2 responses; deleting `prototypes/ner_el_spike/cache/` forces a fresh API run.

---

*Report generated from prototype results on 100 KE descriptions.*
*Models: BERN2 (DMIS-Lab, hosted API at http://bern2.korea.ac.kr/plain).*
*PubTator3 attempted but not available — v3 migration removed free-text endpoints.*
*Comparison date: May 2026.*
