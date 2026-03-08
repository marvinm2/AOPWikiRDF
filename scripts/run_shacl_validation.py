"""Run SHACL validation of AOP-Wiki RDF output against shape definitions.

Validates each data file against its relevant shapes:
- AOPWikiRDF.ttl: AOP, KeyEvent, KER, Stressor, Chemical, GeneAssociation shapes
- AOPWikiRDF-Enriched.ttl: EnrichedXref shape

Results:
- shacl-report.ttl: Full SHACL validation report
- shacl-summary.json: Summary with conforms/violations/warnings/status
- Exit 0 if no sh:Violation results, exit 1 if any violations found
"""

import json
import os
import sys
import time

from rdflib import Graph, Namespace, URIRef

SH = Namespace("http://www.w3.org/ns/shacl#")


def load_shapes(shape_files, shapes_dir):
    """Load specified shape files into a single graph."""
    g = Graph()
    for f in shape_files:
        path = os.path.join(shapes_dir, f)
        if os.path.exists(path):
            g.parse(path, format="turtle")
    return g


def count_results(results_graph):
    """Count violations and warnings in a SHACL results graph."""
    violations = 0
    warnings = 0

    for result in results_graph.subjects(
        URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
        SH.ValidationResult,
    ):
        severity = None
        for _, _, sev in results_graph.triples((result, SH.resultSeverity, None)):
            severity = str(sev)

        if severity and "Violation" in severity:
            violations += 1
        elif severity and "Warning" in severity:
            warnings += 1

    return violations, warnings


def main():
    try:
        import pyshacl
    except ImportError:
        print("ERROR: pyshacl not installed. Run: pip install pyshacl", file=sys.stderr)
        sys.exit(1)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    shapes_dir = os.path.join(base_dir, "shapes")

    # Define which shapes apply to which data files
    validation_sets = [
        {
            "data_file": "AOPWikiRDF.ttl",
            "shapes": [
                "aop-shape.ttl",
                "key-event-shape.ttl",
                "ker-shape.ttl",
                "stressor-shape.ttl",
                "chemical-shape.ttl",
                "gene-association-shape.ttl",
            ],
        },
        {
            "data_file": "AOPWikiRDF-Enriched.ttl",
            "shapes": [
                "enriched-xref-shape.ttl",
            ],
        },
    ]

    total_violations = 0
    total_warnings = 0
    all_reports = Graph()
    start_time = time.time()

    for vset in validation_sets:
        data_path = os.path.join(data_dir, vset["data_file"])
        if not os.path.exists(data_path):
            print(f"WARNING: {data_path} not found, skipping", file=sys.stderr)
            continue

        print(f"\nValidating {vset['data_file']}...", file=sys.stderr)

        # Load data
        data_graph = Graph()
        data_graph.parse(data_path, format="turtle")
        print(f"  Loaded {len(data_graph)} triples", file=sys.stderr)

        # Load relevant shapes
        shapes_graph = load_shapes(vset["shapes"], shapes_dir)
        print(f"  Loaded {len(shapes_graph)} shape triples from {len(vset['shapes'])} files", file=sys.stderr)

        # Run validation
        conforms, results_graph, results_text = pyshacl.validate(
            data_graph,
            shacl_graph=shapes_graph,
            inference=None,
            abort_on_first=False,
        )

        violations, warnings = count_results(results_graph)
        total_violations += violations
        total_warnings += warnings

        print(f"  Conforms: {conforms}", file=sys.stderr)
        print(f"  Violations: {violations}, Warnings: {warnings}", file=sys.stderr)

        # Merge results
        for triple in results_graph:
            all_reports.add(triple)

    elapsed = round(time.time() - start_time, 1)

    # Save full report
    report_path = os.path.join(base_dir, "shacl-report.ttl")
    all_reports.serialize(destination=report_path, format="turtle")
    print(f"\nFull report: {report_path}", file=sys.stderr)

    # Save summary JSON
    summary = {
        "conforms": total_violations == 0,
        "violations": total_violations,
        "warnings": total_warnings,
        "status": "PASS" if total_violations == 0 else "FAIL",
        "elapsed_seconds": elapsed,
    }

    summary_path = os.path.join(base_dir, "shacl-summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary: {summary_path}", file=sys.stderr)

    # Print summary to stdout
    print(f"\n{'='*50}")
    print(f"SHACL Validation Summary")
    print(f"{'='*50}")
    print(f"Status:     {summary['status']}")
    print(f"Violations: {total_violations}")
    print(f"Warnings:   {total_warnings}")
    print(f"Duration:   {elapsed}s")
    print(f"{'='*50}")

    if total_violations > 0:
        print(f"\nFAILED: {total_violations} violation(s) found", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\nPASSED: No violations (warnings are expected for sparse properties)", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
