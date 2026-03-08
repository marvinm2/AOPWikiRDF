"""Integration tests for output separation verification.

Tests validate that the four-file output split maintains expected invariants:
- Pure AOPWikiRDF.ttl has no chemical/protein cross-reference triples
- AOPWikiRDF-Enriched.ttl is valid Turtle with only cross-reference predicates
- VoID metadata declares subsets, licensing, provenance, and example resources
- Combined triple count is reasonable for regression detection
"""

import os
import pytest
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import OWL, RDF, DCTERMS, SKOS, VOID

# Namespaces used in assertions
PAV = Namespace("http://purl.org/pav/")
AOPWIKI = Namespace("http://aopwiki.org/")

# Cross-reference target namespaces that should NOT appear in the pure file
ENRICHED_OBJECT_PREFIXES = [
    "http://identifiers.org/chebi/",
    "http://rdf.chemspider.com/",
    "http://www.wikidata.org/entity/",
    "http://identifiers.org/chembl.compound/",
    "http://identifiers.org/pubchem.compound/",
    "http://identifiers.org/drugbank/",
    "http://identifiers.org/kegg.compound/",
    "http://identifiers.org/lipidmaps/",
    "http://identifiers.org/hmdb/",
    "http://purl.obolibrary.org/obo/PR_",
]

DATA_DIR = "data"
PURE_FILE = os.path.join(DATA_DIR, "AOPWikiRDF.ttl")
ENRICHED_FILE = os.path.join(DATA_DIR, "AOPWikiRDF-Enriched.ttl")
GENES_FILE = os.path.join(DATA_DIR, "AOPWikiRDF-Genes.ttl")
VOID_FILE = os.path.join(DATA_DIR, "AOPWikiRDF-Void.ttl")

skip_unless_data = pytest.mark.skipif(
    not os.path.exists(PURE_FILE),
    reason="Requires generated data files",
)


@skip_unless_data
def test_pure_file_no_crossrefs():
    """AOPWikiRDF.ttl must not contain chemical or protein ontology cross-references."""
    g = Graph()
    g.parse(PURE_FILE, format="turtle")

    # Find owl:sameAs triples whose object falls in enriched namespaces
    violating = []
    for s, p, o in g.triples((None, OWL.sameAs, None)):
        obj_str = str(o)
        for prefix in ENRICHED_OBJECT_PREFIXES:
            if obj_str.startswith(prefix):
                violating.append((str(s), str(o)))
                break

    # Also check skos:exactMatch to enriched namespaces
    for s, p, o in g.triples((None, SKOS.exactMatch, None)):
        obj_str = str(o)
        for prefix in ENRICHED_OBJECT_PREFIXES:
            if obj_str.startswith(prefix):
                violating.append((str(s), str(o)))
                break

    assert len(violating) == 0, (
        f"Pure file contains {len(violating)} cross-reference triples "
        f"that should be in the enriched file. First 5: {violating[:5]}"
    )


@skip_unless_data
def test_enriched_file_valid():
    """AOPWikiRDF-Enriched.ttl must be valid Turtle with only cross-ref predicates."""
    if not os.path.exists(ENRICHED_FILE):
        pytest.skip("Enriched file not yet generated")

    g = Graph()
    g.parse(ENRICHED_FILE, format="turtle")

    triple_count = len(g)
    assert triple_count >= 100, (
        f"Enriched file has only {triple_count} triples; expected at least 100"
    )

    # All predicates should be cross-reference predicates only
    allowed_predicates = {OWL.sameAs, SKOS.exactMatch}
    unexpected = set()
    for s, p, o in g:
        if p not in allowed_predicates:
            unexpected.add(p)

    assert len(unexpected) == 0, (
        f"Enriched file contains non-cross-reference predicates: "
        f"{[str(p) for p in unexpected]}"
    )


@skip_unless_data
def test_enriched_file_header():
    """AOPWikiRDF-Enriched.ttl must have a descriptive Turtle comment header."""
    if not os.path.exists(ENRICHED_FILE):
        pytest.skip("Enriched file not yet generated")

    with open(ENRICHED_FILE, "r") as f:
        header = f.read(2000)  # First 2KB should contain the header

    assert "AOPWikiRDF-Enriched.ttl" in header, (
        "Header must reference the file name"
    )
    assert "Generated" in header or "generated" in header, (
        "Header must contain generation date reference"
    )
    assert "Load alongside" in header or "load alongside" in header or "alongside" in header, (
        "Header must describe relationship to other files"
    )


@skip_unless_data
def test_void_subsets():
    """VoID file must declare subset relationships for all content files."""
    g = Graph()
    g.parse(VOID_FILE, format="turtle")

    # Query for void:subset triples
    subsets = set()
    for s, p, o in g.triples((None, VOID.subset, None)):
        subsets.add(str(o))

    # Check that each content file is declared as a subset
    # The exact URIs depend on naming convention; check for presence of file identifiers
    subset_str = " ".join(subsets)
    assert any("AOPWikiRDF.ttl" in s or "AOPWikiRDF-Pure" in s or s.endswith("AOPWikiRDF") for s in subsets) or "AOPWikiRDF" in subset_str, (
        f"Missing void:subset for pure AOPWikiRDF file. Found subsets: {subsets}"
    )
    assert any("Genes" in s for s in subsets), (
        f"Missing void:subset for Genes file. Found subsets: {subsets}"
    )
    assert any("Enriched" in s for s in subsets), (
        f"Missing void:subset for Enriched file. Found subsets: {subsets}"
    )


@skip_unless_data
def test_void_enrichment():
    """VoID file must have licensing, provenance, and triple counts."""
    g = Graph()
    g.parse(VOID_FILE, format="turtle")

    # Check for CC-BY 4.0 license
    cc_by = URIRef("http://creativecommons.org/licenses/by/4.0/")
    license_triples = list(g.triples((None, DCTERMS.license, cc_by)))
    assert len(license_triples) > 0, (
        "VoID must declare dcterms:license with CC-BY 4.0"
    )

    # Check for pav:importedFrom on enriched subset (BridgeDb provenance)
    imported_triples = list(g.triples((None, PAV.importedFrom, None)))
    assert len(imported_triples) > 0, (
        "VoID must have pav:importedFrom for BridgeDb provenance"
    )

    # Check that at least one void:triples count exists
    triple_count_triples = list(g.triples((None, VOID.triples, None)))
    assert len(triple_count_triples) > 0, (
        "VoID must declare void:triples on at least one subset"
    )
    # Verify the count is a non-zero integer
    for s, p, count_val in triple_count_triples:
        val = int(count_val)
        assert val > 0, f"void:triples count must be positive, got {val}"
        break  # At least one is enough


@skip_unless_data
def test_void_examples():
    """VoID file must have at least 5 distinct example resources."""
    g = Graph()
    g.parse(VOID_FILE, format="turtle")

    examples = set()
    for s, p, o in g.triples((None, VOID.exampleResource, None)):
        examples.add(str(o))

    assert len(examples) >= 5, (
        f"VoID must have at least 5 void:exampleResource entries "
        f"(AOP, KE, KER, Chemical, Stressor). Found {len(examples)}: {examples}"
    )


@skip_unless_data
def test_combined_triple_count():
    """Combined triple count across content files must be reasonable for regression."""
    total = 0

    for filepath in [PURE_FILE, ENRICHED_FILE, GENES_FILE]:
        if not os.path.exists(filepath):
            pytest.skip(f"Missing file: {filepath}")
        g = Graph()
        g.parse(filepath, format="turtle")
        count = len(g)
        total += count
        print(f"  {os.path.basename(filepath)}: {count:,} triples")

    print(f"  TOTAL: {total:,} triples")

    # Regression threshold: combined output should be substantial
    # Current estimates: ~124,901 main + ~75,099 genes + cross-refs
    assert total > 150_000, (
        f"Combined triple count {total:,} is below regression threshold of 150,000. "
        f"This may indicate missing data or broken separation."
    )
