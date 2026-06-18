"""Week-over-week gene/triple delta guard for AOP-Wiki RDF output (QC-01).

The QC workflow validates Turtle SYNTAX (rapper + rdflib parse + static
MIN_TRIPLES floors) but cannot catch a run that parses fine yet silently lost
gene associations (e.g. a BERN2 outage once BERN2 is primary in Phase 7) or
suffered a silent triple drop (the ``<applicability>`` class of loss). This
guard compares freshly generated ``data/*.ttl`` against the last-known-good
TTLs in ``production-rdf-backup/`` and FAILS the run (non-zero exit) if the
gene-association count or the total triple count drops beyond a threshold.

Counting
--------
* Gene associations = number of triples whose predicate is the full URI
  ``http://edamontology.org/data_1025`` (the canonical KE/KER->gene links in
  ``-Genes.ttl``). Counted by exact predicate URI, NOT prefix parsing.
* Total triples = ``len(Graph)`` for each file.

Threshold policy (defaults; tunable via ``--drop-pct``)
-------------------------------------------------------
* Fail if a new count drops below ``(1 - drop_pct) * baseline``.
* Default ``drop_pct`` is 0.05, i.e. a strictly-greater-than 5% drop fails.
  Rationale: a normal weekly AOP-Wiki update moves counts well under 5%; a
  larger drop indicates a silent loss (outage / parser regression). An
  INCREASE always passes; a within-threshold change always passes.
* Total-triple drop is checked for BOTH ``AOPWikiRDF.ttl`` and
  ``AOPWikiRDF-Genes.ttl``; gene-association drop is checked for
  ``AOPWikiRDF-Genes.ttl``.
* A MISSING baseline file OR MISSING new file is a HARD FAIL (cannot prove
  safety).

Output
------
Writes ``qc-delta-report.json`` (baseline vs new counts + computed deltas for
every file, for auditability) and prints a human-readable old-vs-new table.
Exits 0 when no breach, 1 on any breach. Mirrors the JSON-report idiom and CLI
shape of ``scripts/property_audit.py``. Adds no new runtime deps (rdflib only).
"""

import argparse
import json
import os
import sys

from rdflib import Graph, URIRef

# Canonical gene-association predicate (count by exact URI, no prefix parsing).
GENE_PREDICATE = URIRef("http://edamontology.org/data_1025")

# Files checked: total triples on both; gene associations only on -Genes.ttl.
MAIN_FILE = "AOPWikiRDF.ttl"
GENES_FILE = "AOPWikiRDF-Genes.ttl"

DEFAULT_DROP_PCT = 0.05
DEFAULT_NEW_DIR = "data"
DEFAULT_BASELINE_DIR = "production-rdf-backup"
DEFAULT_REPORT_PATH = "qc-delta-report.json"


def load_graph(filepath):
    """Parse a Turtle file into an rdflib Graph.

    Parameters
    ----------
    filepath : str
        Path to a Turtle (.ttl) file.

    Returns
    -------
    rdflib.Graph
    """
    g = Graph()
    g.parse(filepath, format="turtle")
    return g


def count_gene_associations(graph):
    """Return the number of triples with predicate http://edamontology.org/data_1025."""
    return sum(1 for _ in graph.triples((None, GENE_PREDICATE, None)))


def count_triples(graph):
    """Return the total triple count of the graph."""
    return len(graph)


def _delta_pct(baseline, new):
    """Signed fractional change (new - baseline) / baseline.

    Negative = drop, positive = increase. Returns None when baseline is 0
    (cannot compute a percentage against a zero baseline).
    """
    if baseline == 0:
        return None
    return (new - baseline) / baseline


def count_predicate(graph, predicate_uri):
    """Return the number of triples whose predicate is ``predicate_uri``.

    Counts by exact URI (no prefix parsing), exactly the way
    ``count_gene_associations`` counts ``edam:data_1025``. Used by the
    per-element guard to count each fixed-gap element's predicate.
    """
    return sum(1 for _ in graph.triples((None, URIRef(predicate_uri), None)))


def compare_per_element(new_path, baseline_path, element_predicates, drop_pct):
    """Compare per-element predicate counts in new vs baseline TTL.

    For each ``element -> predicate_uri`` pair, count triples by exact URI in
    both graphs and apply the SAME relative floor used for the gene/total
    checks (``baseline > 0 and new < (1 - drop_pct) * baseline``, D-10) — never
    an absolute magic number. A MISSING baseline or new file is a hard breach
    (cannot prove safety), mirroring ``compare``.

    Parameters
    ----------
    new_path : str
        Path to the freshly generated TTL holding the fixed-gap predicates.
    baseline_path : str
        Path to the (HEAD~1) baseline TTL.
    element_predicates : dict
        ``{element_name: predicate_uri}`` map (from coverage-ratchet-baseline).
    drop_pct : float
        Fractional drop threshold; a drop strictly greater than this fraction
        for any tracked predicate is a breach.

    Returns
    -------
    dict
        ``{element: {predicate, baseline_count, new_count, delta_pct,
        breached, reasons}}`` for every tracked element.
    """
    per_element = {}

    missing_reason = None
    if not os.path.exists(baseline_path):
        missing_reason = f"missing baseline file: {baseline_path}"
    elif not os.path.exists(new_path):
        missing_reason = f"missing new file: {new_path}"

    baseline_graph = None
    new_graph = None
    parse_reason = None
    if missing_reason is None:
        try:
            baseline_graph = load_graph(baseline_path)
        except Exception as exc:  # noqa: BLE001 - any parse failure is a hard breach
            parse_reason = f"baseline parse failure ({os.path.basename(baseline_path)}): {exc}"
        if parse_reason is None:
            try:
                new_graph = load_graph(new_path)
            except Exception as exc:  # noqa: BLE001 - any parse failure is a hard breach
                parse_reason = f"new parse failure ({os.path.basename(new_path)}): {exc}"

    for element, predicate in element_predicates.items():
        entry = {
            "predicate": predicate,
            "baseline_count": None,
            "new_count": None,
            "delta_pct": None,
            "breached": False,
            "reasons": [],
        }
        hard_reason = missing_reason or parse_reason
        if hard_reason is not None:
            entry["breached"] = True
            entry["reasons"].append(hard_reason)
            per_element[element] = entry
            continue

        baseline_count = count_predicate(baseline_graph, predicate)
        new_count = count_predicate(new_graph, predicate)
        entry["baseline_count"] = baseline_count
        entry["new_count"] = new_count
        entry["delta_pct"] = _delta_pct(baseline_count, new_count)

        # Relative floor (D-10), identical math to the gene/total checks.
        if baseline_count > 0 and new_count < (1 - drop_pct) * baseline_count:
            entry["breached"] = True
            entry["reasons"].append(
                f"element <{element}> ({predicate}) dropped "
                f"{entry['delta_pct'] * 100:.2f}% "
                f"({baseline_count} -> {new_count}), exceeds {drop_pct * 100:.1f}% threshold"
            )
        per_element[element] = entry

    return per_element


def load_element_predicate_map(coverage_baseline_path):
    """Read the element->predicate map from a coverage-ratchet-baseline.json.

    The baseline JSON is the single source of truth shared by the ratchet and
    the per-element guard (Open Question #2). Expects an ``element_predicates``
    object mapping each fixed-gap element name to its predicate URI.

    Returns
    -------
    dict
        ``{element_name: predicate_uri}``. Empty when the key is absent.
    """
    with open(coverage_baseline_path) as fh:
        data = json.load(fh)
    return data.get("element_predicates", {})


def compare(new_path, baseline_path, drop_pct, check_genes):
    """Compare one new TTL against its baseline.

    Parameters
    ----------
    new_path : str
        Path to the freshly generated TTL.
    baseline_path : str
        Path to the last-known-good baseline TTL.
    drop_pct : float
        Fractional drop threshold. A drop strictly greater than this fraction
        is a breach.
    check_genes : bool
        When True, also compare gene-association (edam:data_1025) counts.

    Returns
    -------
    dict
        Keys: file, baseline_total, new_total, total_delta_pct, breached,
        reasons. When check_genes: baseline_genes, new_genes, gene_delta_pct.
    """
    filename = os.path.basename(new_path)
    result = {
        "file": filename,
        "baseline_total": None,
        "new_total": None,
        "total_delta_pct": None,
        "breached": False,
        "reasons": [],
    }
    if check_genes:
        result["baseline_genes"] = None
        result["new_genes"] = None
        result["gene_delta_pct"] = None

    # Missing baseline or new file is a hard breach (cannot prove safety).
    if not os.path.exists(baseline_path):
        result["breached"] = True
        result["reasons"].append(f"missing baseline file: {baseline_path}")
        return result
    if not os.path.exists(new_path):
        result["breached"] = True
        result["reasons"].append(f"missing new file: {new_path}")
        return result

    try:
        baseline_graph = load_graph(baseline_path)
    except Exception as exc:  # noqa: BLE001 - any parse failure is a hard breach
        result["breached"] = True
        result["reasons"].append(f"baseline parse failure ({filename}): {exc}")
        return result
    try:
        new_graph = load_graph(new_path)
    except Exception as exc:  # noqa: BLE001 - any parse failure is a hard breach
        result["breached"] = True
        result["reasons"].append(f"new parse failure ({filename}): {exc}")
        return result

    baseline_total = count_triples(baseline_graph)
    new_total = count_triples(new_graph)
    result["baseline_total"] = baseline_total
    result["new_total"] = new_total
    result["total_delta_pct"] = _delta_pct(baseline_total, new_total)

    # Total-triple drop check (an increase or within-threshold change passes).
    if baseline_total > 0 and new_total < (1 - drop_pct) * baseline_total:
        result["breached"] = True
        result["reasons"].append(
            f"total triples dropped {result['total_delta_pct'] * 100:.2f}% "
            f"({baseline_total} -> {new_total}), exceeds {drop_pct * 100:.1f}% threshold"
        )

    if check_genes:
        baseline_genes = count_gene_associations(baseline_graph)
        new_genes = count_gene_associations(new_graph)
        result["baseline_genes"] = baseline_genes
        result["new_genes"] = new_genes
        result["gene_delta_pct"] = _delta_pct(baseline_genes, new_genes)

        if baseline_genes > 0 and new_genes < (1 - drop_pct) * baseline_genes:
            result["breached"] = True
            result["reasons"].append(
                f"gene associations (edam:data_1025) dropped "
                f"{result['gene_delta_pct'] * 100:.2f}% "
                f"({baseline_genes} -> {new_genes}), exceeds {drop_pct * 100:.1f}% threshold"
            )

    return result


def _fmt_pct(value):
    """Format a fractional delta as a signed percentage string, or 'n/a'."""
    if value is None:
        return "n/a"
    return f"{value * 100:+.2f}%"


def print_report(report, warn_only=False):
    """Print a human-readable old-vs-new table to stdout.

    When ``warn_only`` is set (D-08 weekly posture), a breach is surfaced as a
    ``WARNING`` rather than ``FAIL`` so CI log readers are not misled into
    investigating a non-failing run that exits 0.
    """
    print("=" * 78)
    print("QC delta guard: new data vs baseline")
    print("=" * 78)
    for entry in report["files"]:
        print(f"\nFile: {entry['file']}")
        print(f"  total triples:     baseline={entry['baseline_total']} "
              f"new={entry['new_total']} delta={_fmt_pct(entry['total_delta_pct'])}")
        if "baseline_genes" in entry:
            print(f"  gene associations: baseline={entry['baseline_genes']} "
                  f"new={entry['new_genes']} delta={_fmt_pct(entry['gene_delta_pct'])}")
        if entry["reasons"]:
            for reason in entry["reasons"]:
                print(f"  BREACH: {reason}")
    if "per_element" in report:
        print("\nPer-element predicate counts (relative floor):")
        for element, entry in report["per_element"].items():
            print(f"  <{element}> ({entry['predicate']}): "
                  f"baseline={entry['baseline_count']} new={entry['new_count']} "
                  f"delta={_fmt_pct(entry['delta_pct'])}")
            for reason in entry["reasons"]:
                print(f"    BREACH: {reason}")
    print()
    if report["breached"]:
        if warn_only:
            print("RESULT: WARNING (delta guard breached, warn-only — not blocking)")
        else:
            print("RESULT: FAIL (delta guard breached)")
    else:
        print("RESULT: PASS (within threshold)")


def run(new_dir, baseline_dir, drop_pct=DEFAULT_DROP_PCT,
        report_path=DEFAULT_REPORT_PATH, per_element=False,
        element_predicates=None):
    """Compare both checked files and write the JSON report.

    Parameters
    ----------
    new_dir : str
        Directory holding the freshly generated TTLs.
    baseline_dir : str
        Directory holding the last-known-good baseline TTLs.
    drop_pct : float
        Fractional drop threshold (default 0.05).
    report_path : str
        Where to write qc-delta-report.json.
    per_element : bool
        When True, ALSO run the per-element predicate-count guard (D-10) using
        ``element_predicates``. Each tracked predicate is counted in the main
        TTL of new_dir vs baseline_dir and held to the same relative floor.
    element_predicates : dict, optional
        ``{element_name: predicate_uri}`` map. When ``per_element`` is True and
        this is None, the per-element pass is a no-op (no elements to check).

    Returns
    -------
    dict
        {"drop_pct", "new_dir", "baseline_dir", "files": [...], "breached": bool}
        and, when ``per_element``, a "per_element" object keyed by element name.
    """
    checks = [
        (MAIN_FILE, False),
        (GENES_FILE, True),
    ]
    file_reports = []
    for filename, check_genes in checks:
        entry = compare(
            os.path.join(new_dir, filename),
            os.path.join(baseline_dir, filename),
            drop_pct=drop_pct,
            check_genes=check_genes,
        )
        file_reports.append(entry)

    aggregated_reasons = []
    for entry in file_reports:
        aggregated_reasons.extend(entry["reasons"])

    report = {
        "drop_pct": drop_pct,
        "new_dir": new_dir,
        "baseline_dir": baseline_dir,
        "files": file_reports,
        "reasons": aggregated_reasons,
        "breached": any(e["breached"] for e in file_reports),
    }

    # Per-element guard (D-10): the fixed-gap predicates live in the main TTL,
    # so count them there. Folds into the same breached/reasons aggregation.
    if per_element:
        element_predicates = element_predicates or {}
        per_element_report = compare_per_element(
            os.path.join(new_dir, MAIN_FILE),
            os.path.join(baseline_dir, MAIN_FILE),
            element_predicates=element_predicates,
            drop_pct=drop_pct,
        )
        report["per_element"] = per_element_report
        for entry in per_element_report.values():
            aggregated_reasons.extend(entry["reasons"])
            if entry["breached"]:
                report["breached"] = True
        report["reasons"] = aggregated_reasons

    with open(report_path, "w") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    return report


def main(argv=None):
    """CLI entry point. Returns 0 on pass, 1 on breach."""
    parser = argparse.ArgumentParser(
        description="Gene/triple delta guard: compare new RDF against the "
                    "last-known-good production-rdf-backup and fail on a "
                    "drop beyond the threshold (QC-01)."
    )
    parser.add_argument("--new-dir", default=DEFAULT_NEW_DIR,
                        help="Directory with freshly generated TTLs (default: data/)")
    parser.add_argument("--baseline-dir", default=DEFAULT_BASELINE_DIR,
                        help="Directory with last-known-good TTLs "
                             "(default: production-rdf-backup/)")
    parser.add_argument("--drop-pct", type=float, default=DEFAULT_DROP_PCT,
                        help="Fractional drop threshold; a drop greater than "
                             "this fails (default: 0.05 = 5%%)")
    parser.add_argument("--report-path", default=DEFAULT_REPORT_PATH,
                        help="Path to write qc-delta-report.json "
                             "(default: qc-delta-report.json)")
    parser.add_argument("--coverage-baseline", default=None,
                        help="Path to scripts/coverage-ratchet-baseline.json. "
                             "When given, also run the per-element predicate "
                             "guard using its element->predicate map (D-10).")
    parser.add_argument("--warn-only", action="store_true",
                        help="On breach, print ::warning:: lines and return 0 "
                             "instead of 1 (weekly warn-not-block posture, D-08).")
    args = parser.parse_args(argv)

    per_element = args.coverage_baseline is not None
    element_predicates = None
    if per_element:
        element_predicates = load_element_predicate_map(args.coverage_baseline)

    report = run(
        new_dir=args.new_dir,
        baseline_dir=args.baseline_dir,
        drop_pct=args.drop_pct,
        report_path=args.report_path,
        per_element=per_element,
        element_predicates=element_predicates,
    )
    print_report(report, warn_only=args.warn_only)

    if not report["breached"]:
        return 0

    # Breach. In warn-only mode (D-08 weekly posture) surface every reason as a
    # ::warning:: and exit 0 so a transient upstream hiccup can't stall the
    # live data release; otherwise fail the job (exit 1).
    if args.warn_only:
        for reason in report["reasons"]:
            print(f"::warning::{reason}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
