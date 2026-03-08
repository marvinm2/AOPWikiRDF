"""Tests verifying documentation covers all required topics."""

import os
import re

import pytest

DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'docs')


class TestSchemaDocumentation:
    """Tests for docs/schema.md completeness."""

    @pytest.fixture(autouse=True)
    def load_schema(self):
        self.schema_path = os.path.join(DOCS_DIR, 'schema.md')

    def test_schema_docs_exist(self):
        assert os.path.isfile(self.schema_path), "docs/schema.md must exist"

    def test_schema_covers_all_entity_types(self):
        with open(self.schema_path, 'r') as f:
            content = f.read()

        entity_types = [
            'AdverseOutcomePathway',
            'KeyEvent',
            'KeyEventRelationship',
            'C54571',           # Stressor (nci:C54571)
            'cheminf',          # Chemical (cheminf:000000/cheminf:000446)
            'edam:data_1025',   # Gene associations
            'owl:sameAs',       # Enriched cross-references
        ]
        for entity_type in entity_types:
            assert entity_type in content, (
                f"docs/schema.md must reference entity type '{entity_type}'"
            )

    def test_schema_has_namespace_table(self):
        with open(self.schema_path, 'r') as f:
            content = f.read()

        # Check for a markdown table with namespace prefixes
        assert '| Prefix' in content, "docs/schema.md must have a namespace prefix table"
        assert 'aopo' in content, "Namespace table must include aopo prefix"
        assert 'http://aopkb.org/aop_ontology#' in content, (
            "Namespace table must include aopo URI"
        )

    def test_schema_has_mermaid_diagram(self):
        with open(self.schema_path, 'r') as f:
            content = f.read()

        assert '```mermaid' in content, "docs/schema.md must contain a mermaid code block"
        assert 'graph' in content, "Mermaid diagram must use graph layout"


class TestSparqlExamples:
    """Tests for docs/sparql-examples.md completeness."""

    @pytest.fixture(autouse=True)
    def load_sparql(self):
        self.sparql_path = os.path.join(DOCS_DIR, 'sparql-examples.md')

    def test_sparql_examples_exist(self):
        assert os.path.isfile(self.sparql_path), "docs/sparql-examples.md must exist"

    def test_sparql_has_minimum_queries(self):
        with open(self.sparql_path, 'r') as f:
            content = f.read()

        select_count = len(re.findall(r'\bSELECT\b', content))
        assert select_count >= 7, (
            f"docs/sparql-examples.md must have at least 7 SELECT queries, found {select_count}"
        )


class TestConversionDocumentation:
    """Tests for docs/conversion.md completeness."""

    @pytest.fixture(autouse=True)
    def load_conversion(self):
        self.conversion_path = os.path.join(DOCS_DIR, 'conversion.md')

    def test_conversion_docs_exist(self):
        assert os.path.isfile(self.conversion_path), "docs/conversion.md must exist"

    def test_conversion_covers_gene_mapping(self):
        with open(self.conversion_path, 'r') as f:
            content = f.read().lower()

        assert 'screening' in content, "Must describe Stage 1: Screening"
        assert 'precision' in content, "Must describe Stage 2: Precision matching"
        assert 'false positive' in content, "Must describe Stage 3: False positive filtering"

    def test_conversion_covers_chemical_mapping(self):
        with open(self.conversion_path, 'r') as f:
            content = f.read()

        assert 'BridgeDb' in content, "Must mention BridgeDb"
        assert 'chemical' in content.lower(), "Must cover chemical mapping"

    def test_conversion_has_examples(self):
        with open(self.conversion_path, 'r') as f:
            content = f.read()

        # Check for concrete gene name examples from production code
        examples_found = sum(1 for gene in ['TP53', 'GCNT2', 'PPIB', 'IV']
                             if gene in content)
        assert examples_found >= 3, (
            f"Must contain at least 3 concrete gene examples, found {examples_found}"
        )
