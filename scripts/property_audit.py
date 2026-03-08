"""SPARQL-based property population audit for AOP-Wiki RDF output files.

Loads each TTL file, discovers rdf:type values and their instance counts,
then for each type finds all properties with population percentages.
Classifies each property severity for SHACL shape generation.

Output: human-readable table to stdout + JSON to scripts/audit-results.json.
"""

import json
import os
import sys
from collections import defaultdict

from rdflib import Graph, Namespace, RDF, URIRef

# Core identity properties that always get sh:Violation regardless of percentage
CORE_IDENTITY_PROPS = {
    "http://purl.org/dc/elements/1.1/identifier",
    "http://purl.org/dc/elements/1.1/title",
    str(RDF.type),
}

# Severity threshold: properties at or above this percentage get sh:Violation
VIOLATION_THRESHOLD = 90.0


def audit_file(filepath):
    """Run property population audit on a single TTL file.

    Parameters
    ----------
    filepath : str
        Path to a Turtle (.ttl) RDF file.

    Returns
    -------
    dict
        Mapping of type URI -> {instances: int, properties: {prop_uri: {count, total, percentage, severity}}}
    """
    g = Graph()
    g.parse(filepath, format="turtle")

    results = {}

    # Step 1: Discover all rdf:type values and instance counts
    type_query = """
    SELECT ?type (COUNT(DISTINCT ?s) AS ?cnt)
    WHERE {
        ?s a ?type .
    }
    GROUP BY ?type
    ORDER BY DESC(?cnt)
    """

    type_counts = {}
    for row in g.query(type_query):
        type_uri = str(row.type)
        type_counts[type_uri] = int(row.cnt)

    # Step 2: For each type, find all properties and their population counts
    for type_uri, instance_count in type_counts.items():
        prop_query = """
        SELECT ?prop (COUNT(DISTINCT ?s) AS ?cnt)
        WHERE {
            ?s a <%s> .
            ?s ?prop ?o .
        }
        GROUP BY ?prop
        ORDER BY DESC(?cnt)
        """ % type_uri

        properties = {}
        for row in g.query(prop_query):
            prop_uri = str(row.prop)
            prop_count = int(row.cnt)
            percentage = round((prop_count / instance_count) * 100, 1)

            # Determine severity
            if prop_uri in CORE_IDENTITY_PROPS:
                severity = "sh:Violation"
            elif percentage >= VIOLATION_THRESHOLD:
                severity = "sh:Violation"
            else:
                severity = "sh:Warning"

            properties[prop_uri] = {
                "count": prop_count,
                "total": instance_count,
                "percentage": percentage,
                "severity": severity,
            }

        results[type_uri] = {
            "instances": instance_count,
            "properties": properties,
        }

    return results


def audit_untyped_subjects(filepath):
    """Audit properties on subjects that have no rdf:type (e.g., enriched xrefs).

    Parameters
    ----------
    filepath : str
        Path to a Turtle (.ttl) RDF file.

    Returns
    -------
    dict or None
        If untyped subjects exist, returns a dict under a synthetic key
        with the same structure as audit_file results. None if no untyped subjects.
    """
    g = Graph()
    g.parse(filepath, format="turtle")

    # Find subjects that have NO rdf:type
    untyped_query = """
    SELECT (COUNT(DISTINCT ?s) AS ?cnt)
    WHERE {
        ?s ?p ?o .
        FILTER NOT EXISTS { ?s a ?type }
    }
    """
    result = list(g.query(untyped_query))
    untyped_count = int(result[0][0]) if result else 0

    if untyped_count == 0:
        return None

    # Get properties used on untyped subjects
    prop_query = """
    SELECT ?prop (COUNT(DISTINCT ?s) AS ?cnt)
    WHERE {
        ?s ?prop ?o .
        FILTER NOT EXISTS { ?s a ?type }
    }
    GROUP BY ?prop
    ORDER BY DESC(?cnt)
    """

    properties = {}
    for row in g.query(prop_query):
        prop_uri = str(row.prop)
        prop_count = int(row.cnt)
        percentage = round((prop_count / untyped_count) * 100, 1)

        if prop_uri in CORE_IDENTITY_PROPS:
            severity = "sh:Violation"
        elif percentage >= VIOLATION_THRESHOLD:
            severity = "sh:Violation"
        else:
            severity = "sh:Warning"

        properties[prop_uri] = {
            "count": prop_count,
            "total": untyped_count,
            "percentage": percentage,
            "severity": severity,
        }

    return {
        "_untyped_subjects": {
            "instances": untyped_count,
            "properties": properties,
        }
    }


def print_report(all_results):
    """Print human-readable audit report to stdout."""
    for filename, file_results in sorted(all_results.items()):
        print(f"\n{'='*70}")
        print(f"File: {filename}")
        print(f"{'='*70}")

        for type_uri, type_data in sorted(file_results.items()):
            instances = type_data["instances"]
            print(f"\n  Type: {type_uri}")
            print(f"  Instances: {instances}")
            print(f"  {'Property':<60} {'Count':>6} {'%':>7} {'Severity':<12}")
            print(f"  {'-'*60} {'-'*6} {'-'*7} {'-'*12}")

            for prop_uri, prop_data in sorted(
                type_data["properties"].items(),
                key=lambda x: -x[1]["percentage"],
            ):
                short_prop = prop_uri
                if len(short_prop) > 58:
                    short_prop = "..." + short_prop[-55:]
                print(
                    f"  {short_prop:<60} {prop_data['count']:>6} "
                    f"{prop_data['percentage']:>6.1f}% {prop_data['severity']:<12}"
                )


def main():
    """Run audit on all three TTL data files and output results."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")

    files = [
        "AOPWikiRDF.ttl",
        "AOPWikiRDF-Genes.ttl",
        "AOPWikiRDF-Enriched.ttl",
    ]

    all_results = {}

    for filename in files:
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            print(f"WARNING: {filepath} not found, skipping")
            continue

        print(f"Auditing {filename}...", file=sys.stderr)

        # Standard typed-subject audit
        typed_results = audit_file(filepath)

        # Also check for untyped subjects (enriched file)
        untyped_results = audit_untyped_subjects(filepath)

        file_results = typed_results
        if untyped_results:
            file_results.update(untyped_results)

        all_results[filename] = file_results

    # Print human-readable report
    print_report(all_results)

    # Write JSON output
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "audit-results.json"
    )
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2, sort_keys=True)

    print(f"\nJSON results written to: {output_path}", file=sys.stderr)
    return all_results


if __name__ == "__main__":
    main()
