# BioBERT NER Prototype

Prototype evaluation of BioBERT-based Named Entity Recognition for gene
detection in AOP-Wiki Key Event descriptions. Compares results against the
current HGNC regex-based three-stage gene mapping approach.

**This is a prototype only -- NOT part of the production pipeline.**

## Prerequisites

- Python 3.11+
- ~440 MB disk space for BioBERT model download on first run
- Access to `data/AOPWikiRDF.ttl` and `data/HGNCgenes.txt` in the project root

## Installation

Install isolated prototype dependencies (do NOT mix with production
`requirements.txt`):

```bash
pip install -r prototypes/biobert_ner/requirements.txt
```

## Usage

Run from the project root directory:

```bash
python prototypes/biobert_ner/run_ner.py
```

Optional arguments:

- `--limit N` -- Process at most N Key Event descriptions (default: 100)
- `--score-threshold F` -- BioBERT confidence threshold (default: 0.5)

## Expected Output

Results are written to `prototypes/biobert_ner/results/`:

| File | Contents |
|------|----------|
| `comparison.json` | Per-KE comparison of BioBERT vs regex gene matches |
| `summary.json` | Aggregate precision, recall, F1 for both methods |
| `disagreements.json` | Cases where the two methods disagree (most interesting) |

## How It Works

1. Extracts KE descriptions from `data/AOPWikiRDF.ttl` via SPARQL query
2. Runs BioBERT NER (`alvaroalon2/biobert_genetic_ner`) on each description
3. Runs the production regex baseline (three-stage algorithm) on each description
4. Compares results: agreement, BioBERT-only finds, regex-only finds
5. Computes aggregate metrics and writes JSON output

## Notes

- First run downloads the BioBERT model from Hugging Face (~440 MB)
- GPU is used automatically if available; CPU works but is slower
- Descriptions are truncated to 512 characters for BioBERT input
- The regex baseline replicates the production three-stage algorithm from
  `src/aopwiki_rdf/mapping/gene_mapper.py`
