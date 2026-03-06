"""Unit tests for the gene mapper module.

Tests cover:
- HGNC dictionary building from real data
- Three-stage false positive filtering
- Live BridgeDb cross-reference resolution
"""

import os
import pytest
import requests

from aopwiki_rdf.mapping.gene_mapper import (
    build_gene_dicts,
    build_gene_xrefs,
    _map_genes_in_text,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HGNC_FILE = os.path.join("data", "HGNCgenes.txt")
HGNC_AVAILABLE = os.path.exists(HGNC_FILE)

BRIDGEDB_URL = "https://webservice.bridgedb.org/Human/"


def _bridgedb_reachable():
    """Check if BridgeDb API is reachable."""
    try:
        r = requests.get(BRIDGEDB_URL, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Test: build_gene_dicts
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HGNC_AVAILABLE, reason="HGNCgenes.txt not present")
def test_build_gene_dicts():
    genedict1, genedict2 = build_gene_dicts(HGNC_FILE)

    # Should have >19000 genes
    assert len(genedict1) > 19000, f"Expected >19000 genes, got {len(genedict1)}"

    # genedict2 should have same keys
    assert set(genedict1.keys()) == set(genedict2.keys())

    # Known gene should be present
    assert "BRCA1" in genedict1, "BRCA1 should be in genedict1"

    # Gene clusters (with @) should be filtered out
    for key in genedict1:
        assert "@" not in key, f"Gene cluster '{key}' should be filtered"


# ---------------------------------------------------------------------------
# Test: false positive filtering via _map_genes_in_text
# ---------------------------------------------------------------------------

def test_map_genes_in_text_false_positives():
    """Test that known false positive patterns are filtered."""
    # Minimal genedict1/genedict2 for testing
    genedict1 = {
        "IV": ["IV"],
        "BRCA1": ["BRCA1"],
        "GCNT2": ["GCNT2", "II"],
    }
    symbols = [" ", "(", ")", "[", "]", ",", "."]
    genedict2 = {}
    for gene_key in genedict1:
        genedict2[gene_key] = []
        for item in genedict1[gene_key]:
            for s1 in symbols:
                for s2 in symbols:
                    genedict2[gene_key].append(s1 + item + s2)

    hgnc_list = []

    # "Complex I" text should NOT match IV gene
    text_complex = "Mitochondrial Complex I and Complex IV are important."
    found = _map_genes_in_text(text_complex, genedict1, hgnc_list, genedict2)
    assert "hgnc:IV" not in found, "IV should be filtered as complex numbering"

    # Text with actual gene name should match
    text_brca = "The BRCA1 gene is involved in DNA repair."
    hgnc_list2 = []
    found2 = _map_genes_in_text(text_brca, genedict1, hgnc_list2, genedict2)
    assert "hgnc:BRCA1" in found2, "BRCA1 should be found"

    # GCNT2 alias "II" in complexes context should be filtered
    text_gcnt2 = "The respiratory chain complexes (I-V) are described."
    hgnc_list3 = []
    found3 = _map_genes_in_text(text_gcnt2, genedict1, hgnc_list3, genedict2)
    assert "hgnc:GCNT2" not in found3, "GCNT2 should be filtered in complexes context"


def test_map_genes_in_text_empty_input():
    """Edge case: empty text returns empty list."""
    result = _map_genes_in_text("", {"A": ["A"]}, [])
    assert result == []

    result2 = _map_genes_in_text("some text", {}, [])
    assert result2 == []


# ---------------------------------------------------------------------------
# Test: build_gene_xrefs (live BridgeDb)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _bridgedb_reachable(),
    reason="BridgeDb API not reachable",
)
def test_build_gene_xrefs_live():
    """Test live BridgeDb xref resolution with known genes."""
    test_genes = ["hgnc:BRCA1", "hgnc:TP53"]
    result = build_gene_xrefs(test_genes, BRIDGEDB_URL, timeout=30)

    assert "geneiddict" in result
    assert "listofentrez" in result
    assert "listofensembl" in result
    assert "listofuniprot" in result

    # Known genes should have cross-references
    assert len(result["listofentrez"]) > 0, "Should find Entrez IDs"
    assert len(result["listofensembl"]) > 0, "Should find Ensembl IDs"
    assert len(result["listofuniprot"]) > 0, "Should find UniProt IDs"

    # geneiddict should have entries for our test genes
    assert "hgnc:BRCA1" in result["geneiddict"]
    assert "hgnc:TP53" in result["geneiddict"]
    assert len(result["geneiddict"]["hgnc:BRCA1"]) > 0
