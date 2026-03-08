"""Unit tests for the property population audit script."""

import os
import sys
import tempfile

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.property_audit import audit_file, CORE_IDENTITY_PROPS, VIOLATION_THRESHOLD


# Small inline Turtle fixture with known types and properties
FIXTURE_TTL = """
@prefix dc: <http://purl.org/dc/elements/1.1/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix aopo: <http://aopkb.org/aop_ontology#> .
@prefix aop: <https://identifiers.org/aop/> .

aop:1 a aopo:AdverseOutcomePathway ;
    dc:identifier "1" ;
    dc:title "Test AOP 1" ;
    rdfs:label "AOP 1 label" .

aop:2 a aopo:AdverseOutcomePathway ;
    dc:identifier "2" ;
    dc:title "Test AOP 2" .

aop:3 a aopo:AdverseOutcomePathway ;
    dc:identifier "3" ;
    dc:title "Test AOP 3" ;
    rdfs:label "AOP 3 label" .
"""


@pytest.fixture
def fixture_file(tmp_path):
    """Write fixture TTL to a temporary file."""
    ttl_file = tmp_path / "test.ttl"
    ttl_file.write_text(FIXTURE_TTL)
    return str(ttl_file)


def test_audit_file_returns_dict(fixture_file):
    """audit_file() returns a dict keyed by type URI."""
    result = audit_file(fixture_file)
    assert isinstance(result, dict)
    assert len(result) > 0


def test_audit_file_has_type_keys(fixture_file):
    """Result contains the expected type URI."""
    result = audit_file(fixture_file)
    aop_type = "http://aopkb.org/aop_ontology#AdverseOutcomePathway"
    assert aop_type in result


def test_audit_file_instance_count(fixture_file):
    """Instance count matches number of typed entities in fixture."""
    result = audit_file(fixture_file)
    aop_type = "http://aopkb.org/aop_ontology#AdverseOutcomePathway"
    assert result[aop_type]["instances"] == 3


def test_audit_file_property_structure(fixture_file):
    """Each property entry has count, total, percentage, severity fields."""
    result = audit_file(fixture_file)
    aop_type = "http://aopkb.org/aop_ontology#AdverseOutcomePathway"
    props = result[aop_type]["properties"]

    for prop_uri, prop_data in props.items():
        assert "count" in prop_data
        assert "total" in prop_data
        assert "percentage" in prop_data
        assert "severity" in prop_data
        assert isinstance(prop_data["count"], int)
        assert isinstance(prop_data["total"], int)
        assert isinstance(prop_data["percentage"], float)
        assert prop_data["severity"] in ("sh:Violation", "sh:Warning")


def test_core_identity_always_violation(fixture_file):
    """Core identity properties (dc:identifier, dc:title, rdf:type) get sh:Violation."""
    result = audit_file(fixture_file)
    aop_type = "http://aopkb.org/aop_ontology#AdverseOutcomePathway"
    props = result[aop_type]["properties"]

    dc_identifier = "http://purl.org/dc/elements/1.1/identifier"
    dc_title = "http://purl.org/dc/elements/1.1/title"
    rdf_type = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

    assert props[dc_identifier]["severity"] == "sh:Violation"
    assert props[dc_title]["severity"] == "sh:Violation"
    assert props[rdf_type]["severity"] == "sh:Violation"


def test_sparse_property_gets_warning(fixture_file):
    """Properties below 90% population get sh:Warning."""
    result = audit_file(fixture_file)
    aop_type = "http://aopkb.org/aop_ontology#AdverseOutcomePathway"
    props = result[aop_type]["properties"]

    # rdfs:label is only on 2 of 3 instances = 66.7%
    rdfs_label = "http://www.w3.org/2000/01/rdf-schema#label"
    assert props[rdfs_label]["percentage"] < VIOLATION_THRESHOLD
    assert props[rdfs_label]["severity"] == "sh:Warning"


def test_full_population_gets_violation(fixture_file):
    """Properties at 100% population get sh:Violation."""
    result = audit_file(fixture_file)
    aop_type = "http://aopkb.org/aop_ontology#AdverseOutcomePathway"
    props = result[aop_type]["properties"]

    dc_identifier = "http://purl.org/dc/elements/1.1/identifier"
    assert props[dc_identifier]["percentage"] == 100.0
    assert props[dc_identifier]["severity"] == "sh:Violation"


def test_percentage_calculation(fixture_file):
    """Population percentage is correctly calculated."""
    result = audit_file(fixture_file)
    aop_type = "http://aopkb.org/aop_ontology#AdverseOutcomePathway"
    props = result[aop_type]["properties"]

    rdfs_label = "http://www.w3.org/2000/01/rdf-schema#label"
    # 2 out of 3 = 66.7%
    assert props[rdfs_label]["count"] == 2
    assert props[rdfs_label]["total"] == 3
    assert abs(props[rdfs_label]["percentage"] - 66.7) < 0.1
