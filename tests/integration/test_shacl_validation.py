"""Integration tests for SHACL validation of AOP-Wiki RDF output.

Tests verify that SHACL shapes correctly validate the RDF data files
and that validation completes within acceptable time limits.
"""

import os
import subprocess
import sys
import time

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
SHAPES_DIR = os.path.join(PROJECT_ROOT, "shapes")
GENE_SHAPE = os.path.join(SHAPES_DIR, "gene-association-shape.ttl")
GENE_FIXTURE = os.path.join(
    PROJECT_ROOT, "data-test", "gene-association-provenance-fixture.ttl"
)

# The four Phase-7 predicate paths the regenerated gene-association shape must
# cover so the new BERN2 provenance triples ship validated (GENE-06 / PROV-01,
# threat T-07-07).
NEW_PREDICATE_PATHS = [
    ":geneDetectedByNER",
    ":geneDetectedByRegex",
    ":isFeaturedMethod",
    "prov:",
]


def _has_pyshacl():
    try:
        import pyshacl
        return True
    except ImportError:
        return False


def _has_data_files():
    return (
        os.path.exists(os.path.join(DATA_DIR, "AOPWikiRDF.ttl"))
        and os.path.exists(os.path.join(DATA_DIR, "AOPWikiRDF-Enriched.ttl"))
    )


def _has_shape_files():
    return os.path.exists(os.path.join(SHAPES_DIR, "aop-shape.ttl"))


requires_pyshacl = pytest.mark.skipif(
    not _has_pyshacl(), reason="pyshacl not installed"
)
requires_data = pytest.mark.skipif(
    not _has_data_files(), reason="data TTL files not available"
)
requires_shapes = pytest.mark.skipif(
    not _has_shape_files(), reason="SHACL shape files not generated"
)


@requires_pyshacl
@requires_data
@requires_shapes
def test_shacl_validates_aop_entities():
    """Load AOPWikiRDF.ttl + aop-shape.ttl, run pyshacl, assert no violations."""
    import pyshacl
    from rdflib import Graph

    data = Graph()
    data.parse(os.path.join(DATA_DIR, "AOPWikiRDF.ttl"), format="turtle")

    shapes = Graph()
    shapes.parse(os.path.join(SHAPES_DIR, "aop-shape.ttl"), format="turtle")

    conforms, results_graph, results_text = pyshacl.validate(
        data, shacl_graph=shapes, inference=None, abort_on_first=False,
    )

    # Check for violations specifically (warnings are acceptable)
    from rdflib import Namespace
    SH = Namespace("http://www.w3.org/ns/shacl#")
    RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")

    violations = 0
    for result in results_graph.subjects(RDF.type, SH.ValidationResult):
        for _, _, sev in results_graph.triples((result, SH.resultSeverity, None)):
            if "Violation" in str(sev):
                violations += 1

    assert violations == 0, f"Found {violations} violations in AOP shape validation"


@requires_pyshacl
@requires_data
@requires_shapes
def test_no_violations_on_current_data():
    """Run full validation runner script, assert exit code 0."""
    result = subprocess.run(
        [sys.executable, os.path.join(PROJECT_ROOT, "scripts", "run_shacl_validation.py")],
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, f"Validation failed:\n{result.stderr}\n{result.stdout}"


def _has_gene_fixture():
    return os.path.exists(GENE_FIXTURE) and os.path.exists(GENE_SHAPE)


requires_gene_fixture = pytest.mark.skipif(
    not _has_gene_fixture(),
    reason="flag-on gene fixture or regenerated gene-association shape missing",
)


@requires_gene_fixture
def test_gene_shape_covers_new_bern2_predicates():
    """Regenerated gene-association shape references the four Phase-7 predicate paths.

    Guards T-07-07: a shape regenerated against a flag-OFF genes file would
    silently omit these, letting the new predicates ship unvalidated.
    """
    content = open(GENE_SHAPE).read()
    for path in NEW_PREDICATE_PATHS:
        assert path in content, (
            f"gene-association-shape.ttl is missing the new predicate path "
            f"'{path}' -- was it regenerated against the flag-ON fixture?"
        )
    # The new predicates must render prefixed (not as full <URI>).
    assert "<https://aopwiki.rdf.bigcat-bioinformatics.org/geneDetectedBy" not in content
    assert "<http://www.w3.org/ns/prov#" not in content.split("@prefix")[-1]


@requires_pyshacl
@requires_gene_fixture
def test_flag_on_fixture_conforms_to_gene_shape():
    """pyshacl validates the flag-on fixture green against the regenerated shape."""
    import pyshacl
    from rdflib import Graph, Namespace

    data = Graph().parse(GENE_FIXTURE, format="turtle")
    shapes = Graph().parse(GENE_SHAPE, format="turtle")

    conforms, results_graph, results_text = pyshacl.validate(
        data, shacl_graph=shapes, inference=None, abort_on_first=False,
    )

    SH = Namespace("http://www.w3.org/ns/shacl#")
    RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
    violations = 0
    for result in results_graph.subjects(RDF.type, SH.ValidationResult):
        for _, _, sev in results_graph.triples((result, SH.resultSeverity, None)):
            if "Violation" in str(sev):
                violations += 1

    assert violations == 0, (
        f"flag-on fixture produced {violations} violation(s) against the "
        f"regenerated gene-association shape:\n{results_text}"
    )


# Phase 8 / Plan 08-03: the flag-on label fixture + the regenerated chemical and
# gene-association shapes carrying the rdfs:label constraint (D-09 / LABEL-04).
LABEL_FIXTURE = os.path.join(PROJECT_ROOT, "data-test", "iri-label-fixture.ttl")
CHEMICAL_SHAPE = os.path.join(SHAPES_DIR, "chemical-shape.ttl")


def _has_label_fixture():
    return (
        os.path.exists(LABEL_FIXTURE)
        and os.path.exists(CHEMICAL_SHAPE)
        and os.path.exists(GENE_SHAPE)
    )


requires_label_fixture = pytest.mark.skipif(
    not _has_label_fixture(),
    reason="flag-on label fixture or regenerated chemical/gene shape missing",
)


@requires_label_fixture
def test_chemical_and_gene_shapes_carry_rdfs_label_constraint():
    """Regenerated chemical + gene-association shapes constrain rdfs:label (D-06/D-09).

    The chemical shape gains the constraint via a ChemicalXrefShape sourced from
    the flag-on fixture; the gene-association shape already carries it on the
    gene-identifier subjects. Both prove the rdfs:label sh:property is present.
    """
    chem = open(CHEMICAL_SHAPE).read()
    gene = open(GENE_SHAPE).read()
    assert "sh:path rdfs:label" in chem, (
        "chemical-shape.ttl is missing the rdfs:label constraint -- was it "
        "regenerated against the flag-on iri-label-fixture.ttl?"
    )
    assert "sh:path rdfs:label" in gene, (
        "gene-association-shape.ttl is missing the rdfs:label constraint."
    )


@requires_pyshacl
@requires_label_fixture
def test_label_fixture_conforms_to_regenerated_shapes():
    """pyshacl validates the flag-on label fixture green against the regenerated
    chemical + gene-association shapes (no sh:Violation)."""
    import pyshacl
    from rdflib import Graph, Namespace

    data = Graph().parse(LABEL_FIXTURE, format="turtle")
    shapes = Graph()
    shapes.parse(CHEMICAL_SHAPE, format="turtle")
    shapes.parse(GENE_SHAPE, format="turtle")

    conforms, results_graph, results_text = pyshacl.validate(
        data, shacl_graph=shapes, inference=None, abort_on_first=False,
    )

    SH = Namespace("http://www.w3.org/ns/shacl#")
    RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
    violations = 0
    for result in results_graph.subjects(RDF.type, SH.ValidationResult):
        for _, _, sev in results_graph.triples((result, SH.resultSeverity, None)):
            if "Violation" in str(sev):
                violations += 1

    assert violations == 0, (
        f"flag-on label fixture produced {violations} violation(s) against the "
        f"regenerated chemical + gene-association shapes:\n{results_text}"
    )


@requires_pyshacl
@requires_data
@requires_shapes
def test_completes_under_timeout():
    """Assert validation completes in under 300 seconds."""
    start = time.time()
    result = subprocess.run(
        [sys.executable, os.path.join(PROJECT_ROOT, "scripts", "run_shacl_validation.py")],
        capture_output=True, text=True, timeout=300,
    )
    elapsed = time.time() - start
    assert elapsed < 300, f"Validation took {elapsed:.1f}s, exceeds 300s limit"
    assert result.returncode == 0, f"Validation failed during timeout test"
