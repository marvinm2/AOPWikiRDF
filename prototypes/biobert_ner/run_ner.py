#!/usr/bin/env python3
"""BioBERT NER prototype: compare gene detection against regex baseline.

Extracts Key Event descriptions from AOPWikiRDF.ttl, runs BioBERT NER and
the production regex-based gene mapping, and produces comparison metrics.

Usage:
    python prototypes/biobert_ner/run_ner.py [--limit N] [--score-threshold F]

Requires: transformers, torch, rdflib (see requirements.txt)
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

_MISSING_DEPS = []
try:
    import torch  # noqa: F401
except ImportError:
    _MISSING_DEPS.append("torch")
try:
    from transformers import pipeline as hf_pipeline  # noqa: F401
except ImportError:
    _MISSING_DEPS.append("transformers")
try:
    from rdflib import Graph  # noqa: F401
except ImportError:
    _MISSING_DEPS.append("rdflib")

if _MISSING_DEPS:
    print(
        "Missing dependencies: " + ", ".join(_MISSING_DEPS) + "\n"
        "Install with: pip install -r prototypes/biobert_ner/requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RDF_FILE = PROJECT_ROOT / "data" / "AOPWikiRDF.ttl"
HGNC_FILE = PROJECT_ROOT / "data" / "HGNCgenes.txt"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

BIOBERT_MODEL = "alvaroalon2/biobert_genetic_ner"

# SPARQL to extract KE descriptions (with filter for non-trivial text)
KE_SPARQL = """\
PREFIX aopo: <http://aopkb.org/aop_ontology#>
PREFIX dc:   <http://purl.org/dc/elements/1.1/>

SELECT ?ke ?title ?description
WHERE {
    ?ke a aopo:KeyEvent ;
        dc:title ?title ;
        dc:description ?description .
    FILTER(STRLEN(STR(?description)) > 50)
}
LIMIT %d
"""


# ---------------------------------------------------------------------------
# Section 1: Extract KE descriptions from RDF
# ---------------------------------------------------------------------------

def extract_ke_descriptions(limit: int = 100) -> list[dict]:
    """Extract KE descriptions from AOPWikiRDF.ttl via SPARQL."""
    print(f"Loading RDF from {RDF_FILE} ...")
    g = Graph()
    g.parse(str(RDF_FILE), format="turtle")
    print(f"  Loaded {len(g)} triples")

    query = KE_SPARQL % limit
    results = g.query(query)

    ke_data = []
    for row in results:
        ke_uri = str(row.ke)
        title = str(row.title)
        description = str(row.description)
        ke_data.append({
            "ke_uri": ke_uri,
            "title": title,
            "description": description,
        })

    print(f"  Extracted {len(ke_data)} KE descriptions (limit={limit})")
    return ke_data


# ---------------------------------------------------------------------------
# Section 2: BioBERT NER
# ---------------------------------------------------------------------------

def run_biobert_ner(
    ke_data: list[dict],
    score_threshold: float = 0.5,
) -> dict[str, list[dict]]:
    """Run BioBERT NER on each KE description.

    Returns mapping of ke_uri -> list of detected entities.
    """
    print(f"\nLoading BioBERT model ({BIOBERT_MODEL}) ...")
    ner = hf_pipeline(
        "ner",
        model=BIOBERT_MODEL,
        aggregation_strategy="simple",
    )
    print("  Model loaded.")

    results: dict[str, list[dict]] = {}
    total = len(ke_data)

    for idx, ke in enumerate(ke_data, 1):
        # Truncate to 512 characters for model input
        text = ke["description"][:512]
        try:
            entities = ner(text)
        except Exception as e:
            print(f"  [{idx}/{total}] Error on {ke['ke_uri']}: {e}")
            results[ke["ke_uri"]] = []
            continue

        # Filter by score threshold and collect gene entities
        gene_entities = []
        for ent in entities:
            if ent["score"] >= score_threshold:
                gene_entities.append({
                    "word": ent["word"],
                    "score": round(float(ent["score"]), 4),
                    "entity_group": ent.get("entity_group", "UNKNOWN"),
                    "start": ent.get("start"),
                    "end": ent.get("end"),
                })

        results[ke["ke_uri"]] = gene_entities
        if idx % 20 == 0 or idx == total:
            print(f"  [{idx}/{total}] Processed, found {len(gene_entities)} entities")

    return results


# ---------------------------------------------------------------------------
# Section 3: Regex baseline (replicates production three-stage algorithm)
# ---------------------------------------------------------------------------

# False-positive filter constants (from src/aopwiki_rdf/mapping/gene_mapper.py)
SINGLE_LETTER_ALIASES = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
ROMAN_NUMERAL_PATTERN = re.compile(r"\b[IVX]+\b")


def _is_false_positive(
    matched_alias: str, context: str
) -> bool:
    """Simplified false positive filter matching production logic."""
    stripped = matched_alias.strip()

    # Filter 1: Single letter aliases
    if stripped in SINGLE_LETTER_ALIASES:
        return True

    # Filter 2: Roman numerals
    if ROMAN_NUMERAL_PATTERN.fullmatch(stripped):
        return True

    # Filter 3: Short symbols in bracket context
    if len(stripped) <= 2 and any(c in context for c in "()[]{}"):
        return True

    # Filter 4: Gene-specific patterns
    if stripped == "IV" and (
        "Complex I" in context or "(I\u2013V)" in context
    ):
        return True
    if stripped == "II" and (
        "(I\u2013V)" in context or "complexes" in context.lower()
    ):
        return True

    return False


def build_gene_dicts() -> tuple[dict, dict, dict]:
    """Build gene dictionaries from HGNC file (production algorithm)."""
    print(f"\nBuilding gene dictionaries from {HGNC_FILE} ...")
    symbols_list = [" ", "(", ")", "[", "]", ",", "."]
    genedict1: dict[str, list[str]] = {}
    genedict2: dict[str, list[str]] = {}
    symbol_lookup: dict[str, str] = {}

    hgnc_id_pattern = re.compile(r"^HGNC:(\d+)$")

    with open(HGNC_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "HGNC ID" in line and "Approved symbol" in line:
                continue
            parts = line.rstrip("\n").split("\t")
            m = hgnc_id_pattern.match(parts[0])
            if not m:
                continue
            hgnc_id = m.group(1)
            gene_symbol = parts[1]

            if "@" in gene_symbol:
                continue

            symbol_lookup[hgnc_id] = gene_symbol
            genedict1[hgnc_id] = [gene_symbol]
            genedict2[hgnc_id] = []

            if len(parts) > 2 and parts[2]:
                genedict1[hgnc_id].append(parts[2])

            for item in parts[3:]:
                if item:
                    for name in item.split(", "):
                        genedict1[hgnc_id].append(name)

            for item in genedict1[hgnc_id]:
                for s1 in symbols_list:
                    for s2 in symbols_list:
                        genedict2[hgnc_id].append(s1 + item + s2)

    print(f"  Built dictionaries: {len(genedict1)} genes")
    return genedict1, genedict2, symbol_lookup


def run_regex_baseline(
    ke_data: list[dict],
    genedict1: dict,
    genedict2: dict,
    symbol_lookup: dict,
) -> dict[str, list[str]]:
    """Run three-stage regex gene mapping on each KE description.

    Returns mapping of ke_uri -> list of matched gene symbols.
    """
    print("\nRunning regex baseline ...")
    results: dict[str, list[str]] = {}
    total = len(ke_data)

    for idx, ke in enumerate(ke_data, 1):
        text = ke["description"]
        found_genes: list[str] = []

        for gene_key in genedict1:
            # Stage 1: Screen with genedict1
            stage1_hit = False
            for item in genedict1[gene_key]:
                if item in text:
                    stage1_hit = True
                    break

            if not stage1_hit:
                continue

            # Stage 2: Precision match with genedict2
            hgnc_id = "hgnc:" + gene_key
            if gene_key in genedict2:
                for item in genedict2[gene_key]:
                    if item in text and hgnc_id not in found_genes:
                        # Stage 3: False positive filter
                        match_index = text.find(item)
                        ctx_start = max(0, match_index - 50)
                        ctx_end = min(len(text), match_index + len(item) + 50)
                        context = text[ctx_start:ctx_end]

                        matched_alias = (
                            item.strip(" ()[],.") if len(item) >= 3
                            else item[1:-1] if len(item) == 3
                            else item
                        )

                        if not _is_false_positive(matched_alias, context):
                            found_genes.append(hgnc_id)
                        break

        # Convert HGNC IDs to symbols for readability
        gene_symbols = []
        for hid in found_genes:
            numeric = hid.replace("hgnc:", "")
            sym = symbol_lookup.get(numeric, numeric)
            gene_symbols.append(sym)

        results[ke["ke_uri"]] = gene_symbols
        if idx % 20 == 0 or idx == total:
            print(f"  [{idx}/{total}] Processed, found {len(gene_symbols)} genes")

    return results


# ---------------------------------------------------------------------------
# Section 4: Comparison
# ---------------------------------------------------------------------------

def normalize_biobert_entities(entities: list[dict]) -> set[str]:
    """Extract unique gene name strings from BioBERT entities."""
    names = set()
    for ent in entities:
        word = ent["word"].strip().replace("##", "")
        if word and len(word) > 1:  # skip single chars
            names.add(word.upper())
    return names


def compare_results(
    ke_data: list[dict],
    biobert_results: dict[str, list[dict]],
    regex_results: dict[str, list[str]],
) -> tuple[list[dict], dict, list[dict]]:
    """Compare BioBERT and regex results per KE.

    Returns (comparisons, summary, disagreements).
    """
    comparisons = []
    disagreements = []

    total_biobert_only = 0
    total_regex_only = 0
    total_both = 0
    total_biobert_count = 0
    total_regex_count = 0

    for ke in ke_data:
        uri = ke["ke_uri"]
        biobert_genes = normalize_biobert_entities(
            biobert_results.get(uri, [])
        )
        regex_genes = set(g.upper() for g in regex_results.get(uri, []))

        both = biobert_genes & regex_genes
        biobert_only = biobert_genes - regex_genes
        regex_only = regex_genes - biobert_genes

        total_biobert_only += len(biobert_only)
        total_regex_only += len(regex_only)
        total_both += len(both)
        total_biobert_count += len(biobert_genes)
        total_regex_count += len(regex_genes)

        entry = {
            "ke_uri": uri,
            "title": ke["title"],
            "biobert_genes": sorted(biobert_genes),
            "regex_genes": sorted(regex_genes),
            "both": sorted(both),
            "biobert_only": sorted(biobert_only),
            "regex_only": sorted(regex_only),
        }
        comparisons.append(entry)

        if biobert_only or regex_only:
            disagreements.append(entry)

    # Compute summary metrics
    # Using regex as ground truth proxy for precision/recall estimation
    # (since we don't have manual annotations for all KEs)
    biobert_precision = (
        total_both / total_biobert_count if total_biobert_count > 0 else 0.0
    )
    biobert_recall = (
        total_both / total_regex_count if total_regex_count > 0 else 0.0
    )
    biobert_f1 = (
        2 * biobert_precision * biobert_recall
        / (biobert_precision + biobert_recall)
        if (biobert_precision + biobert_recall) > 0
        else 0.0
    )

    # Regex self-comparison (100% by definition when regex is ground truth)
    regex_precision = 1.0
    regex_recall = 1.0
    regex_f1 = 1.0

    summary = {
        "total_ke_descriptions": len(ke_data),
        "total_genes_found_by_biobert": total_biobert_count,
        "total_genes_found_by_regex": total_regex_count,
        "genes_found_by_both": total_both,
        "genes_found_by_biobert_only": total_biobert_only,
        "genes_found_by_regex_only": total_regex_only,
        "biobert_metrics_vs_regex_baseline": {
            "precision": round(biobert_precision, 4),
            "recall": round(biobert_recall, 4),
            "f1": round(biobert_f1, 4),
            "note": (
                "Precision/recall computed using regex results as proxy "
                "ground truth. For true metrics, manual annotation is needed."
            ),
        },
        "regex_metrics_self": {
            "precision": regex_precision,
            "recall": regex_recall,
            "f1": regex_f1,
            "note": "Trivially 1.0 since regex is used as its own baseline.",
        },
        "disagreement_count": len(disagreements),
        "agreement_rate": round(
            (len(ke_data) - len(disagreements)) / len(ke_data), 4
        ) if ke_data else 0.0,
    }

    return comparisons, summary, disagreements


# ---------------------------------------------------------------------------
# Section 5: Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="BioBERT NER prototype: compare gene detection approaches"
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Max number of KE descriptions to process (default: 100)",
    )
    parser.add_argument(
        "--score-threshold", type=float, default=0.5,
        help="BioBERT confidence score threshold (default: 0.5)",
    )
    args = parser.parse_args()

    # Validate input files exist
    if not RDF_FILE.exists():
        print(f"Error: RDF file not found: {RDF_FILE}", file=sys.stderr)
        print("Run from the project root directory.", file=sys.stderr)
        sys.exit(1)
    if not HGNC_FILE.exists():
        print(f"Error: HGNC file not found: {HGNC_FILE}", file=sys.stderr)
        sys.exit(1)

    # Step 1: Extract KE descriptions
    ke_data = extract_ke_descriptions(limit=args.limit)
    if not ke_data:
        print("No KE descriptions found. Check RDF file.", file=sys.stderr)
        sys.exit(1)

    # Step 2: Run BioBERT NER
    t0 = time.time()
    biobert_results = run_biobert_ner(ke_data, score_threshold=args.score_threshold)
    biobert_time = time.time() - t0
    biobert_per_ke = biobert_time / len(ke_data) if ke_data else 0

    # Step 3: Run regex baseline
    genedict1, genedict2, symbol_lookup = build_gene_dicts()
    t0 = time.time()
    regex_results = run_regex_baseline(ke_data, genedict1, genedict2, symbol_lookup)
    regex_time = time.time() - t0
    regex_per_ke = regex_time / len(ke_data) if ke_data else 0

    # Step 4: Compare results
    comparisons, summary, disagreements = compare_results(
        ke_data, biobert_results, regex_results
    )

    # Add timing to summary
    summary["runtime"] = {
        "biobert_total_seconds": round(biobert_time, 2),
        "biobert_per_ke_seconds": round(biobert_per_ke, 4),
        "regex_total_seconds": round(regex_time, 2),
        "regex_per_ke_seconds": round(regex_per_ke, 4),
        "regex_includes_dict_build": False,
        "note": "BioBERT time includes model loading on first call.",
    }

    # Step 5: Write results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    comparison_path = RESULTS_DIR / "comparison.json"
    summary_path = RESULTS_DIR / "summary.json"
    disagreements_path = RESULTS_DIR / "disagreements.json"

    with open(comparison_path, "w", encoding="utf-8") as f:
        json.dump(comparisons, f, indent=2, ensure_ascii=False)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with open(disagreements_path, "w", encoding="utf-8") as f:
        json.dump(disagreements, f, indent=2, ensure_ascii=False)

    # Print summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"KE descriptions processed: {summary['total_ke_descriptions']}")
    print(f"Genes found by BioBERT:    {summary['total_genes_found_by_biobert']}")
    print(f"Genes found by regex:      {summary['total_genes_found_by_regex']}")
    print(f"Found by both:             {summary['genes_found_by_both']}")
    print(f"BioBERT only:              {summary['genes_found_by_biobert_only']}")
    print(f"Regex only:                {summary['genes_found_by_regex_only']}")
    print(f"Disagreement cases:        {summary['disagreement_count']}")
    print()
    print("BioBERT metrics (vs regex baseline):")
    bm = summary["biobert_metrics_vs_regex_baseline"]
    print(f"  Precision: {bm['precision']:.4f}")
    print(f"  Recall:    {bm['recall']:.4f}")
    print(f"  F1:        {bm['f1']:.4f}")
    print()
    print("Runtime:")
    rt = summary["runtime"]
    print(f"  BioBERT: {rt['biobert_total_seconds']:.2f}s total "
          f"({rt['biobert_per_ke_seconds']:.4f}s/KE)")
    print(f"  Regex:   {rt['regex_total_seconds']:.2f}s total "
          f"({rt['regex_per_ke_seconds']:.4f}s/KE)")
    print()
    print(f"Results written to {RESULTS_DIR}/")
    print(f"  - {comparison_path.name}")
    print(f"  - {summary_path.name}")
    print(f"  - {disagreements_path.name}")


if __name__ == "__main__":
    main()
