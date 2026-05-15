# NER + Entity Linking Spike (BERN2 + PubTator3)

Spike to evaluate **NER + Entity Linking** tools as a possible drop-in replacement
for the regex-based gene mapping in `src/aopwiki_rdf/mapping/gene_mapper.py`.

The Phase 5-04 BioBERT prototype (`prototypes/biobert_ner/`) concluded that
plain BioBERT cannot replace regex because it emits raw text spans rather
than HGNC IDs. This spike tries two tools that include entity linking:

- **BERN2** (DMIS-Lab) — NER + normalisation to NCBI Gene IDs, hosted API at
  `http://bern2.korea.ac.kr/plain`.
- **PubTator3** (NIH) — NER + normalisation, hosted API at
  `https://www.ncbi.nlm.nih.gov/research/pubtator3-api/annotate/`.

Both tools produce normalised database IDs; NCBI Gene → HGNC is a one-hop
lookup via BridgeDb (the same path the production pipeline already uses).

**This is a prototype only — NOT part of the production pipeline.**

## Prerequisites

- Python 3.11+
- Internet access (hosted APIs)
- `data/AOPWikiRDF.ttl` and `data/HGNCgenes.txt` in the project root
  (already shipped in the repo)

## Installation

Install isolated dependencies (do not mix with production `requirements.txt`):

```bash
pip install -r prototypes/ner_el_spike/requirements.txt
```

## Usage

Run from the project root:

```bash
python prototypes/ner_el_spike/run_spike.py --limit 100
```

Optional flags:

- `--limit N` — Process at most N Key Event descriptions (default: 100).
- `--skip-bern2` / `--skip-pubtator` — Skip one tool (useful if one is down).
- `--clear-cache` — Force re-query of the hosted APIs (default: cache hit on rerun).

API responses are cached per-KE under `prototypes/ner_el_spike/cache/<tool>/`,
so re-running the spike is cheap and respectful of the hosted services.

## Expected Output

`prototypes/ner_el_spike/results/`:

| File | Contents |
|------|----------|
| `comparison.json` | Per-KE comparison across regex / BERN2 / PubTator |
| `summary.json` | Aggregate stats, pairwise overlap, precision/recall/F1 |
| `disagreements.json` | KEs where at least two methods disagree |
| `REPORT.md` | Hand-written final report (see Phase 5-04 for structure template) |

## Decision criteria

The REPORT's recommendation follows three rules (from the plan):

- **Go (replace regex)** — A tool produces HGNC IDs at ≥ regex precision AND
  ≥ regex recall, and projected full-corpus throughput fits the weekly
  `rdfgeneration.yml` budget (< 30 min for ~10 K KEs).
- **Hybrid** — A tool catches HGNC-mapped genes regex misses, with
  acceptable precision but lower recall. Layer it on top of regex.
- **No-go** — HGNC mapping yield < 30 % for both tools, or precision is
  unworkable, or throughput would break the weekly workflow.
