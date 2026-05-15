#!/usr/bin/env python3
"""NER + Entity Linking spike: evaluate BERN2 and PubTator3 against the
regex gene mapper as a drop-in replacement for HGNC gene identification.

Phase 5-04 showed that plain BioBERT NER produces raw text spans that
cannot be mapped to HGNC. This spike tries two tools that include entity
linking and emit normalised NCBI Gene IDs (one BridgeDb hop from HGNC):

    - BERN2 (DMIS-Lab) hosted API
    - PubTator3 (NIH) hosted API

Usage:
    python prototypes/ner_el_spike/run_spike.py [--limit N]
                                                [--skip-bern2 | --skip-pubtator]
                                                [--clear-cache]

Requires: requests, rdflib (see requirements.txt).
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Iterable

_MISSING = []
try:
    import requests
except ImportError:
    _MISSING.append("requests")
try:
    from rdflib import Graph
except ImportError:
    _MISSING.append("rdflib")
if _MISSING:
    print(
        "Missing dependencies: " + ", ".join(_MISSING) + "\n"
        "Install: pip install -r prototypes/ner_el_spike/requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RDF_FILE = PROJECT_ROOT / "data" / "AOPWikiRDF.ttl"
HGNC_FILE = PROJECT_ROOT / "data" / "HGNCgenes.txt"
SPIKE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SPIKE_DIR / "results"
CACHE_DIR = SPIKE_DIR / "cache"

BERN2_URL = "http://bern2.korea.ac.kr/plain"
PUBTATOR3_URL = (
    "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/annotate/"
    "publications/export/biocjson"
)
BRIDGEDB_URL = "https://webservice.bridgedb.org/Human/"

# SPARQL: KE descriptions, deterministic order via ORDER BY ?ke
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
ORDER BY ?ke
LIMIT %d
"""


# ---------------------------------------------------------------------------
# Section 1: Extract KE descriptions from RDF
# ---------------------------------------------------------------------------

def extract_ke_descriptions(limit: int = 100) -> list[dict]:
    print(f"Loading RDF from {RDF_FILE} ...")
    g = Graph()
    g.parse(str(RDF_FILE), format="turtle")
    print(f"  Loaded {len(g)} triples")
    results = g.query(KE_SPARQL % limit)
    ke_data = [
        {"ke_uri": str(r.ke), "title": str(r.title), "description": str(r.description)}
        for r in results
    ]
    print(f"  Extracted {len(ke_data)} KE descriptions (limit={limit})")
    return ke_data


# ---------------------------------------------------------------------------
# Section 2: Regex baseline (ported from prototypes/biobert_ner/run_ner.py
#            to keep this spike comparable to Phase 5-04)
# ---------------------------------------------------------------------------

SINGLE_LETTER_ALIASES = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
ROMAN_NUMERAL_PATTERN = re.compile(r"\b[IVX]+\b")


def _is_false_positive(matched_alias: str, context: str) -> bool:
    s = matched_alias.strip()
    if s in SINGLE_LETTER_ALIASES:
        return True
    if ROMAN_NUMERAL_PATTERN.fullmatch(s):
        return True
    if len(s) <= 2 and any(c in context for c in "()[]{}"):
        return True
    if s == "IV" and ("Complex I" in context or "(I–V)" in context):
        return True
    if s == "II" and ("(I–V)" in context or "complexes" in context.lower()):
        return True
    return False


def build_gene_dicts() -> tuple[dict, dict, dict]:
    print(f"\nBuilding gene dictionaries from {HGNC_FILE} ...")
    symbols_list = [" ", "(", ")", "[", "]", ",", "."]
    genedict1: dict[str, list[str]] = {}
    genedict2: dict[str, list[str]] = {}
    symbol_lookup: dict[str, str] = {}
    hgnc_id_pattern = re.compile(r"^(?:HGNC:)?(\d+)$")
    with open(HGNC_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "HGNC ID" in line and "Approved symbol" in line:
                continue
            parts = line.rstrip("\n").split("\t")
            m = hgnc_id_pattern.match(parts[0].strip())
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
) -> dict[str, set[str]]:
    """Return ke_uri -> set of HGNC numeric IDs (canonical comparison key)."""
    print("\nRunning regex baseline ...")
    results: dict[str, set[str]] = {}
    total = len(ke_data)
    for idx, ke in enumerate(ke_data, 1):
        text = ke["description"]
        found_ids: set[str] = set()
        for gene_key in genedict1:
            stage1_hit = any(item in text for item in genedict1[gene_key])
            if not stage1_hit:
                continue
            if gene_key in genedict2:
                for item in genedict2[gene_key]:
                    if item in text:
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
                            found_ids.add(gene_key)
                        break
        results[ke["ke_uri"]] = found_ids
        if idx % 20 == 0 or idx == total:
            print(f"  [{idx}/{total}] regex found {len(found_ids)} genes")
    return results


# ---------------------------------------------------------------------------
# Section 3: HTTP helpers with disk cache
# ---------------------------------------------------------------------------

def _cache_key(text: str) -> str:
    """Deterministic 12-char cache filename for arbitrary text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _cached_post(
    url: str,
    payload: dict,
    cache_subdir: str,
    timeout: int = 60,
    sleep_after: float = 1.0,
) -> dict | None:
    """POST JSON to ``url``; cache responses under cache/<subdir>/<sha>.json.

    Returns parsed JSON, or None on failure (with the failure reason cached
    so subsequent runs don't retry).
    """
    cache_dir = CACHE_DIR / cache_subdir
    cache_dir.mkdir(parents=True, exist_ok=True)
    text = payload.get("text") or payload.get("description") or json.dumps(payload, sort_keys=True)
    cache_path = cache_dir / f"{_cache_key(text)}.json"
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache_path.unlink()  # corrupt; refetch

    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        data = {"_error": str(e), "_status": getattr(r, "status_code", None) if "r" in dir() else None}

    cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if sleep_after > 0:
        time.sleep(sleep_after)
    return data


# ---------------------------------------------------------------------------
# Section 4: BERN2
# ---------------------------------------------------------------------------

def _bern2_query_single(text: str) -> dict:
    """One BERN2 POST. Returns parsed JSON or {"_error": "..."}."""
    try:
        r = requests.post(BERN2_URL, json={"text": text}, timeout=120)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        return {"_error": str(e), "_status": getattr(r, "status_code", None) if "r" in dir() else None}


def _bern2_with_chunking(text: str, max_chars: int = 1500) -> dict:
    """Query BERN2; on JSON-truncation error, split text by sentence and merge.

    BERN2's hosted API truncates the JSON response for very long inputs
    (observed JSON-decode error past char ~5170). Splitting at sentence
    boundaries keeps each request small enough to return valid JSON.
    """
    cache_dir = CACHE_DIR / "bern2"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{_cache_key(text)}.json"
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache_path.unlink()

    # First try: single call
    data = _bern2_query_single(text)
    time.sleep(1.0)
    if "_error" not in data:
        cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    # Fallback: split into sentence-ish chunks and merge annotations
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    buf = ""
    for s in sentences:
        if len(buf) + len(s) + 1 > max_chars and buf:
            chunks.append(buf)
            buf = s
        else:
            buf = (buf + " " + s).strip()
    if buf:
        chunks.append(buf)

    merged_annotations: list[dict] = []
    seen_keys: set[tuple] = set()  # de-dup across chunks
    errors: list[str] = []
    char_offset = 0
    for chunk in chunks:
        sub = _bern2_query_single(chunk)
        time.sleep(1.0)
        if "_error" in sub:
            errors.append(sub["_error"])
            char_offset += len(chunk) + 1
            continue
        for ann in sub.get("annotations", []):
            mention = ann.get("mention", "")
            ids_tuple = tuple(sorted(ann.get("id", []) or []))
            key = (ann.get("obj"), mention, ids_tuple)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged_annotations.append(ann)
        char_offset += len(chunk) + 1

    if not merged_annotations and errors:
        merged = {"_error": "; ".join(errors[:3])}
    else:
        merged = {"annotations": merged_annotations}
    cache_path.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
    return merged


def run_bern2(ke_data: list[dict]) -> dict[str, dict]:
    """Return ke_uri -> {entities: [...], ncbi_gene_ids: set[str], error: str|None}."""
    print(f"\nRunning BERN2 NER+EL ({BERN2_URL}) ...")
    out: dict[str, dict] = {}
    total = len(ke_data)
    for idx, ke in enumerate(ke_data, 1):
        text = ke["description"][:5000]
        data = _bern2_with_chunking(text)
        if isinstance(data, dict) and "_error" in data:
            err = data["_error"]
            out[ke["ke_uri"]] = {"entities": [], "ncbi_gene_ids": set(), "error": err}
            if idx <= 3:
                print(f"  [{idx}/{total}] BERN2 error: {err}")
            continue

        annotations = data.get("annotations", []) if isinstance(data, dict) else []
        entities = []
        ncbi_ids: set[str] = set()
        for ann in annotations:
            if ann.get("obj") != "gene":
                continue
            mention = ann.get("mention", "")
            ids = ann.get("id", []) or []
            for raw in ids:
                if raw.startswith("NCBIGene:"):
                    ncbi_ids.add(raw[len("NCBIGene:"):])
                elif raw.startswith("EntrezGene:"):
                    ncbi_ids.add(raw[len("EntrezGene:"):])
            entities.append({"mention": mention, "ids": ids, "type": ann.get("obj")})
        out[ke["ke_uri"]] = {"entities": entities, "ncbi_gene_ids": ncbi_ids, "error": None}
        if idx % 10 == 0 or idx == total:
            print(f"  [{idx}/{total}] BERN2: {len(entities)} gene entities, "
                  f"{len(ncbi_ids)} NCBI IDs")
    return out


# ---------------------------------------------------------------------------
# Section 5: PubTator3
# ---------------------------------------------------------------------------

def run_pubtator(ke_data: list[dict]) -> dict[str, dict]:
    """Stub. PubTator3 no longer offers a free-text annotate REST endpoint.

    As of the PubTator v2 → v3 migration, the public API only supports
    PMID-based publication annotations (``/publications/export``). The
    free-text endpoints (``/annotate``, ``/findEntityId``, ``/freetext``)
    all return ``{"detail": "This resource is not available"}``. GNorm2 and
    AIONER, the v3 components that handle gene NER+EL, also lack a hosted
    REST API at the time of this spike.

    This function is kept as a stub so the comparison framework keeps
    three columns (regex / BERN2 / PubTator) and the limitation is visible
    in the output rather than hidden.
    """
    print(f"\nSkipping PubTator3 — free-text endpoint removed in v3 migration. "
          f"See REPORT.md for details.")
    return {
        ke["ke_uri"]: {
            "entities": [],
            "ncbi_gene_ids": set(),
            "error": "PubTator3 free-text REST endpoint not available "
                     "(see REPORT.md)",
        }
        for ke in ke_data
    }


# ---------------------------------------------------------------------------
# Section 6: NCBI Gene -> HGNC via BridgeDb
# ---------------------------------------------------------------------------

def bridgedb_ncbi_to_hgnc(
    ncbi_ids: Iterable[str], chunk_size: int = 100,
) -> dict[str, str]:
    """Map a flat list of NCBI Gene numeric IDs to HGNC numeric IDs.

    POSTs to ``{BRIDGEDB_URL}xrefsBatch/L`` (system L = Entrez Gene).
    Returns {ncbi_id: hgnc_numeric_id}. Missing mappings are absent from
    the result.
    """
    ncbi_list = sorted({s for s in ncbi_ids if s and s.isdigit()})
    if not ncbi_list:
        return {}
    print(f"\nMapping {len(ncbi_list)} NCBI Gene IDs to HGNC via BridgeDb ...")
    out: dict[str, str] = {}
    cache_dir = CACHE_DIR / "bridgedb"
    cache_dir.mkdir(parents=True, exist_ok=True)

    for i in range(0, len(ncbi_list), chunk_size):
        chunk = ncbi_list[i:i + chunk_size]
        cache_path = cache_dir / f"{_cache_key(','.join(chunk))}.txt"
        if cache_path.exists():
            response_text = cache_path.read_text(encoding="utf-8")
        else:
            try:
                # BridgeDb batch: newline-separated IDs in body, system code in URL
                r = requests.post(
                    f"{BRIDGEDB_URL}xrefsBatch/L",
                    data="\n".join(chunk),
                    timeout=60,
                )
                r.raise_for_status()
                response_text = r.text
                cache_path.write_text(response_text, encoding="utf-8")
                time.sleep(0.2)
            except requests.RequestException as e:
                print(f"  BridgeDb batch error (chunk {i//chunk_size}): {e}")
                continue

        # Parse response: NCBI_ID\tEntrez Gene\tHac:HGNC:N,H:SYMBOL,En:ENSG...
        # The HGNC numeric ID lives under "Hac:HGNC:N" (system code "Hac",
        # HGNC Accession); the bare "H:" prefix carries the gene symbol.
        for line in response_text.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            ncbi_id = parts[0]
            xrefs = parts[2]
            if xrefs == "N/A":
                continue
            for token in xrefs.split(","):
                if token.startswith("Hac:HGNC:"):
                    hgnc_numeric = token[len("Hac:HGNC:"):]
                    if hgnc_numeric.isdigit():
                        out[ncbi_id] = hgnc_numeric
                    break
    print(f"  Mapped {len(out)} / {len(ncbi_list)} NCBI Gene IDs to HGNC "
          f"({100*len(out)/len(ncbi_list):.1f}% yield)")
    return out


# ---------------------------------------------------------------------------
# Section 7: Three-way comparison
# ---------------------------------------------------------------------------

def compare_three_way(
    ke_data: list[dict],
    regex_hgnc: dict[str, set[str]],
    bern2_results: dict[str, dict],
    pubtator_results: dict[str, dict],
    ncbi_to_hgnc: dict[str, str],
    symbol_lookup: dict[str, str],
) -> tuple[list[dict], dict, list[dict]]:
    comparisons: list[dict] = []
    disagreements: list[dict] = []

    counts = {"regex": 0, "bern2": 0, "pubtator": 0}
    yields = {
        "bern2_ncbi_total": 0, "bern2_hgnc_mapped": 0,
        "pubtator_ncbi_total": 0, "pubtator_hgnc_mapped": 0,
    }
    overlaps = {
        "regex_bern2": 0,
        "regex_pubtator": 0,
        "bern2_pubtator": 0,
        "all_three": 0,
        "regex_only": 0,
        "bern2_only": 0,
        "pubtator_only": 0,
    }

    for ke in ke_data:
        uri = ke["ke_uri"]

        regex_set = set(regex_hgnc.get(uri, set()))

        bern2_ncbi = bern2_results.get(uri, {}).get("ncbi_gene_ids", set())
        bern2_hgnc = {ncbi_to_hgnc[n] for n in bern2_ncbi if n in ncbi_to_hgnc}
        yields["bern2_ncbi_total"] += len(bern2_ncbi)
        yields["bern2_hgnc_mapped"] += len(bern2_hgnc)

        pubtator_ncbi = pubtator_results.get(uri, {}).get("ncbi_gene_ids", set())
        pubtator_hgnc = {ncbi_to_hgnc[n] for n in pubtator_ncbi if n in ncbi_to_hgnc}
        yields["pubtator_ncbi_total"] += len(pubtator_ncbi)
        yields["pubtator_hgnc_mapped"] += len(pubtator_hgnc)

        counts["regex"] += len(regex_set)
        counts["bern2"] += len(bern2_hgnc)
        counts["pubtator"] += len(pubtator_hgnc)

        rb = regex_set & bern2_hgnc
        rp = regex_set & pubtator_hgnc
        bp = bern2_hgnc & pubtator_hgnc
        all3 = regex_set & bern2_hgnc & pubtator_hgnc
        overlaps["regex_bern2"] += len(rb)
        overlaps["regex_pubtator"] += len(rp)
        overlaps["bern2_pubtator"] += len(bp)
        overlaps["all_three"] += len(all3)
        overlaps["regex_only"] += len(regex_set - bern2_hgnc - pubtator_hgnc)
        overlaps["bern2_only"] += len(bern2_hgnc - regex_set - pubtator_hgnc)
        overlaps["pubtator_only"] += len(pubtator_hgnc - regex_set - bern2_hgnc)

        def syms(hgnc_set: set[str]) -> list[str]:
            return sorted(symbol_lookup.get(h, h) for h in hgnc_set)

        entry = {
            "ke_uri": uri,
            "title": ke["title"],
            "regex_hgnc": sorted(regex_set),
            "regex_symbols": syms(regex_set),
            "bern2_hgnc": sorted(bern2_hgnc),
            "bern2_symbols": syms(bern2_hgnc),
            "bern2_mentions": [e["mention"] for e in bern2_results.get(uri, {}).get("entities", [])],
            "pubtator_hgnc": sorted(pubtator_hgnc),
            "pubtator_symbols": syms(pubtator_hgnc),
            "pubtator_mentions": [e["mention"] for e in pubtator_results.get(uri, {}).get("entities", [])],
            "bern2_error": bern2_results.get(uri, {}).get("error"),
            "pubtator_error": pubtator_results.get(uri, {}).get("error"),
        }
        comparisons.append(entry)
        if regex_set != bern2_hgnc or regex_set != pubtator_hgnc:
            disagreements.append(entry)

    # Precision / recall using regex as proxy ground truth
    def pr_f1(method_count: int, overlap_with_regex: int) -> dict:
        precision = (overlap_with_regex / method_count) if method_count > 0 else 0.0
        recall = (overlap_with_regex / counts["regex"]) if counts["regex"] > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}

    bern2_yield = (
        100 * yields["bern2_hgnc_mapped"] / yields["bern2_ncbi_total"]
        if yields["bern2_ncbi_total"] > 0 else 0.0
    )
    pubtator_yield = (
        100 * yields["pubtator_hgnc_mapped"] / yields["pubtator_ncbi_total"]
        if yields["pubtator_ncbi_total"] > 0 else 0.0
    )

    summary = {
        "methods": ["regex", "bern2", "pubtator"],
        "total_ke_descriptions": len(ke_data),
        "aggregate_stats": {
            "regex": {"total_hgnc_ids_found": counts["regex"]},
            "bern2": {
                "total_hgnc_ids_found": counts["bern2"],
                "total_ncbi_entities_detected": yields["bern2_ncbi_total"],
                "hgnc_yield_pct": round(bern2_yield, 2),
            },
            "pubtator": {
                "total_hgnc_ids_found": counts["pubtator"],
                "total_ncbi_entities_detected": yields["pubtator_ncbi_total"],
                "hgnc_yield_pct": round(pubtator_yield, 2),
            },
        },
        "pairwise_overlap": overlaps,
        "per_method_pr_f1": {
            "regex": {"precision": 1.0, "recall": 1.0, "f1": 1.0,
                      "note": "Trivially 1.0; regex is the baseline."},
            "bern2": {
                **pr_f1(counts["bern2"], overlaps["regex_bern2"]),
                "note": "vs regex baseline."},
            "pubtator": {
                **pr_f1(counts["pubtator"], overlaps["regex_pubtator"]),
                "note": "vs regex baseline."},
        },
        "disagreement_count": len(disagreements),
        "agreement_rate": round(
            (len(ke_data) - len(disagreements)) / len(ke_data), 4
        ) if ke_data else 0.0,
    }

    return comparisons, summary, disagreements


# ---------------------------------------------------------------------------
# Section 8: Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--skip-bern2", action="store_true")
    parser.add_argument("--skip-pubtator", action="store_true")
    parser.add_argument("--clear-cache", action="store_true")
    args = parser.parse_args()

    if not RDF_FILE.exists():
        print(f"Error: {RDF_FILE} not found. Run from project root.", file=sys.stderr)
        sys.exit(1)
    if not HGNC_FILE.exists():
        print(f"Error: {HGNC_FILE} not found.", file=sys.stderr)
        sys.exit(1)

    if args.clear_cache and CACHE_DIR.exists():
        import shutil
        shutil.rmtree(CACHE_DIR)
        print(f"Cleared cache at {CACHE_DIR}")

    ke_data = extract_ke_descriptions(limit=args.limit)
    if not ke_data:
        print("No KE descriptions found.", file=sys.stderr)
        sys.exit(1)

    genedict1, genedict2, symbol_lookup = build_gene_dicts()

    t0 = time.time()
    regex_hgnc = run_regex_baseline(ke_data, genedict1, genedict2, symbol_lookup)
    regex_time = time.time() - t0

    if args.skip_bern2:
        print("\nSkipping BERN2 (--skip-bern2).")
        bern2_results: dict[str, dict] = {ke["ke_uri"]: {"entities": [], "ncbi_gene_ids": set(), "error": "skipped"} for ke in ke_data}
        bern2_time = 0.0
    else:
        t0 = time.time()
        bern2_results = run_bern2(ke_data)
        bern2_time = time.time() - t0

    if args.skip_pubtator:
        print("\nSkipping PubTator (--skip-pubtator).")
        pubtator_results: dict[str, dict] = {ke["ke_uri"]: {"entities": [], "ncbi_gene_ids": set(), "error": "skipped"} for ke in ke_data}
        pubtator_time = 0.0
    else:
        t0 = time.time()
        pubtator_results = run_pubtator(ke_data)
        pubtator_time = time.time() - t0

    # Collect all NCBI IDs to normalise in a single BridgeDb batch
    all_ncbi: set[str] = set()
    for d in bern2_results.values():
        all_ncbi |= d.get("ncbi_gene_ids", set())
    for d in pubtator_results.values():
        all_ncbi |= d.get("ncbi_gene_ids", set())
    ncbi_to_hgnc = bridgedb_ncbi_to_hgnc(all_ncbi)

    comparisons, summary, disagreements = compare_three_way(
        ke_data, regex_hgnc, bern2_results, pubtator_results, ncbi_to_hgnc, symbol_lookup,
    )

    summary["runtime"] = {
        "regex_total_seconds": round(regex_time, 2),
        "bern2_total_seconds": round(bern2_time, 2),
        "pubtator_total_seconds": round(pubtator_time, 2),
        "per_ke_seconds": {
            "regex": round(regex_time / len(ke_data), 4),
            "bern2": round(bern2_time / len(ke_data), 4),
            "pubtator": round(pubtator_time / len(ke_data), 4),
        },
        "note": "NER+EL times include hosted-API latency + 1s rate-limit sleep.",
    }
    summary["bern2_error_count"] = sum(
        1 for d in bern2_results.values() if d.get("error")
    )
    summary["pubtator_error_count"] = sum(
        1 for d in pubtator_results.values() if d.get("error")
    )

    # Serialise sets as lists for JSON compatibility
    def jsonable(o):
        if isinstance(o, set):
            return sorted(o)
        raise TypeError(f"Not JSON serialisable: {type(o).__name__}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "comparison.json").write_text(
        json.dumps(comparisons, indent=2, ensure_ascii=False, default=jsonable),
        encoding="utf-8",
    )
    (RESULTS_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=jsonable),
        encoding="utf-8",
    )
    (RESULTS_DIR / "disagreements.json").write_text(
        json.dumps(disagreements, indent=2, ensure_ascii=False, default=jsonable),
        encoding="utf-8",
    )

    # Console summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"KE descriptions processed: {summary['total_ke_descriptions']}")
    print()
    print(f"{'Method':10} {'HGNC':>6} {'NCBI':>6} {'yield%':>7}  prec  recall   F1")
    for m in ("regex", "bern2", "pubtator"):
        stats = summary["aggregate_stats"][m]
        prf = summary["per_method_pr_f1"][m]
        ncbi = stats.get("total_ncbi_entities_detected", "-")
        yld = stats.get("hgnc_yield_pct", "-")
        print(f"{m:10} {stats['total_hgnc_ids_found']:>6} "
              f"{str(ncbi):>6} {str(yld):>7}  "
              f"{prf['precision']:.3f}  {prf['recall']:.3f}  {prf['f1']:.3f}")
    print()
    print("Pairwise overlap:")
    for k, v in summary["pairwise_overlap"].items():
        print(f"  {k:18} {v}")
    print()
    print("Runtime:")
    rt = summary["runtime"]
    for k in ("regex", "bern2", "pubtator"):
        print(f"  {k:10} {rt[k + '_total_seconds']:>7.2f}s "
              f"({rt['per_ke_seconds'][k]:.4f}s/KE)")
    print()
    print(f"Errors: BERN2={summary['bern2_error_count']}, "
          f"PubTator={summary['pubtator_error_count']}")
    print()
    print(f"Results written to {RESULTS_DIR}/")


if __name__ == "__main__":
    main()
