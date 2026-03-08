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
