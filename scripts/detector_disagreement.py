"""Rank gene mappings by regex/NER detector disagreement (issue #109).

Finding alias collisions has been manual: someone notices that ``ROS`` is
matching ROS1 and adds it to the stoplist. The published RDF already carries a
signal that surfaces them automatically.

Both detectors are materialised -- ``:geneDetectedByRegex`` and
``:geneDetectedByNER``. A gene the dictionary asserts on many entities that
BERN2 never confirms is overwhelmingly a collision, because a context-aware
model declines exactly what a context-free string match cannot.

This is a PRECISION HEURISTIC, NOT GROUND TRUTH. NER silence does not prove a
false positive: BERN2 has its own recall gaps and has had zero-output weeks. The
ranking exists to gate human review, and must never drive an automatic drop.
It also cannot see collisions both detectors make.

Usage
-----
    python scripts/detector_disagreement.py [--genes-file data/AOPWikiRDF-Genes.ttl]
                                            [--min-regex-entities 10]
                                            [--max-agreement 0.10]
                                            [--report-path gene-disagreement.json]
"""

import argparse
import json
import re
import sys

DEFAULT_GENES_FILE = "data/AOPWikiRDF-Genes.ttl"
DEFAULT_REPORT_PATH = "gene-disagreement.json"

# Thresholds chosen to surface the known-good cases (ROS1, TBATA), not tuned.
DEFAULT_MIN_REGEX_ENTITIES = 10
DEFAULT_MAX_AGREEMENT = 0.10

_ENTITY_RE = re.compile(r"^(aop\.(?:events|relationships):\d+)", re.MULTILINE)
_HGNC_RE = re.compile(r"hgnc:(\d+)")


def parse_detector_sets(text: str) -> tuple[dict, dict]:
    """Return ``({gene: {entities}}, {gene: {entities}})`` for regex and NER.

    Parsed with regexes rather than rdflib: this reads one predicate pair out of
    a 200k-triple file, and a full graph parse costs ~30s for no added accuracy.
    """
    regex_hits: dict[str, set] = {}
    ner_hits: dict[str, set] = {}

    # Split into per-subject blocks, then read each detector predicate's objects.
    starts = [m.start() for m in _ENTITY_RE.finditer(text)]
    starts.append(len(text))
    for i in range(len(starts) - 1):
        block = text[starts[i]:starts[i + 1]]
        entity = _ENTITY_RE.match(block).group(1)
        for predicate, target in (
            ("geneDetectedByRegex", regex_hits),
            ("geneDetectedByNER", ner_hits),
        ):
            match = re.search(
                re.escape(predicate) + r"(.*?)(?=;|\.\s*\n)", block, re.S
            )
            if not match:
                continue
            for gene in _HGNC_RE.findall(match.group(1)):
                target.setdefault(gene, set()).add(entity)

    return regex_hits, ner_hits


def rank_candidates(regex_hits, ner_hits, min_regex_entities, max_agreement):
    """Return collision candidates, most regex-asserted first."""
    candidates = []
    for gene, entities in regex_hits.items():
        if len(entities) < min_regex_entities:
            continue
        confirmed = entities & ner_hits.get(gene, set())
        agreement = len(confirmed) / len(entities)
        if agreement <= max_agreement:
            candidates.append({
                "gene": f"hgnc:{gene}",
                "regex_entities": len(entities),
                "ner_confirmed": len(confirmed),
                "agreement": round(agreement, 4),
            })
    candidates.sort(key=lambda c: (-c["regex_entities"], c["gene"]))
    return candidates


def load_symbols(path="data/HGNCgenes.txt") -> dict:
    """Return ``{numeric_hgnc_id: (symbol, [aliases])}`` for annotation."""
    symbols = {}
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                parts = line.rstrip("\n").split("\t")
                if len(parts) > 4 and parts[0].isdigit():
                    aliases = [
                        a for a in parts[3].split(", ") + parts[4].split(", ") if a
                    ]
                    symbols[parts[0]] = (parts[1], aliases)
    except OSError:
        pass  # annotation is a convenience, not a requirement
    return symbols


def format_report(candidates, symbols) -> str:
    """Render the ranking as a markdown table for a human reviewer."""
    if not candidates:
        return "No candidates above threshold.\n"

    lines = [
        "| gene | symbol | regex entities | NER confirmed | agreement | short aliases |",
        "|---|---|---:|---:|---:|---|",
    ]
    for candidate in candidates:
        numeric = candidate["gene"].split(":")[1]
        symbol, aliases = symbols.get(numeric, ("?", []))
        short = ", ".join(f"`{a}`" for a in aliases if len(a) <= 4) or "—"
        lines.append(
            f"| {candidate['gene']} | {symbol} | {candidate['regex_entities']} "
            f"| {candidate['ner_confirmed']} | {candidate['agreement']:.0%} | {short} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--genes-file", default=DEFAULT_GENES_FILE)
    parser.add_argument("--min-regex-entities", type=int,
                        default=DEFAULT_MIN_REGEX_ENTITIES)
    parser.add_argument("--max-agreement", type=float,
                        default=DEFAULT_MAX_AGREEMENT)
    parser.add_argument("--report-path", default=DEFAULT_REPORT_PATH)
    args = parser.parse_args(argv)

    try:
        with open(args.genes_file, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        print(f"ERROR: cannot read {args.genes_file}: {exc}", file=sys.stderr)
        return 1

    regex_hits, ner_hits = parse_detector_sets(text)
    if not ner_hits:
        # Without NER output there is no disagreement to measure. Not an error:
        # BERN2 is optional and has had zero-output weeks.
        print("::warning::No :geneDetectedByNER triples found; "
              "disagreement ranking needs both detectors. Skipping.")
        return 0

    candidates = rank_candidates(
        regex_hits, ner_hits, args.min_regex_entities, args.max_agreement,
    )
    symbols = load_symbols()

    report = {
        "min_regex_entities": args.min_regex_entities,
        "max_agreement": args.max_agreement,
        "regex_genes": len(regex_hits),
        "ner_genes": len(ner_hits),
        "candidate_count": len(candidates),
        "candidate_pairs": sum(c["regex_entities"] for c in candidates),
        "candidates": candidates,
    }
    with open(args.report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    print(f"Regex-detected genes: {len(regex_hits)}  NER-detected: {len(ner_hits)}")
    print(f"Collision candidates (regex >= {args.min_regex_entities} entities, "
          f"agreement <= {args.max_agreement:.0%}): {len(candidates)} genes, "
          f"{report['candidate_pairs']} regex-asserted pairs\n")
    print(format_report(candidates, symbols))
    print(f"Report written to {args.report_path}")
    print("\nNOTE: a heuristic for review, not ground truth. NER silence is not "
          "proof of a false positive -- verify before stoplisting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
