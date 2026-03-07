"""Unit tests for the gene mapper module.

Tests cover:
- HGNC dictionary building from real data (numeric HGNC ID keys)
- Three-stage false positive filtering
- Live BridgeDb cross-reference resolution with symbol_lookup
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
# Test: build_gene_dicts (numeric HGNC ID keys + symbol_lookup)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HGNC_AVAILABLE, reason="HGNCgenes.txt not present")
def test_build_gene_dicts():
    result = build_gene_dicts(HGNC_FILE)

    # Must return 3-tuple (genedict1, genedict2, symbol_lookup)
    assert len(result) == 3, f"Expected 3-tuple, got {len(result)}-tuple"
    genedict1, genedict2, symbol_lookup = result

    # Should have >19000 genes
    assert len(genedict1) > 19000, f"Expected >19000 genes, got {len(genedict1)}"

    # genedict2 should have same keys
    assert set(genedict1.keys()) == set(genedict2.keys())

    # Keys should be numeric strings (e.g. "5"), not symbols (e.g. "A1BG")
    assert "5" in genedict1, "Numeric HGNC ID '5' (A1BG) should be in genedict1"
    assert "A1BG" not in genedict1, "Symbol 'A1BG' should NOT be a key"

    # genedict1["5"] should contain "A1BG" as first search term
    assert genedict1["5"][0] == "A1BG", "Symbol should be first element in value list"

    # symbol_lookup should map numeric ID to symbol
    assert symbol_lookup["5"] == "A1BG", "symbol_lookup['5'] should be 'A1BG'"

    # Gene clusters (with @) should be filtered out
    for key in genedict1:
        assert key.isdigit(), f"Key '{key}' should be numeric"

    # genedict2 keys match genedict1 keys
    assert set(genedict2.keys()) == set(genedict1.keys())


@pytest.mark.skipif(not HGNC_AVAILABLE, reason="HGNCgenes.txt not present")
def test_build_gene_dicts_no_invalid_hgnc_ids():
    """Lines without valid HGNC:NNNN in column 0 are skipped."""
    genedict1, genedict2, symbol_lookup = build_gene_dicts(HGNC_FILE)
    # All keys should be purely numeric strings
    for key in genedict1:
        assert key.isdigit(), f"Key '{key}' is not a valid numeric HGNC ID"


# ---------------------------------------------------------------------------
# Test: false positive filtering via _map_genes_in_text (numeric-keyed dicts)
# ---------------------------------------------------------------------------

def test_map_genes_in_text_false_positives():
    """Test that known false positive patterns are filtered with numeric-keyed dicts."""
    # Minimal genedict1/genedict2 using numeric IDs as keys
    genedict1 = {
        "100": ["IV"],           # IV gene -> numeric key "100"
        "1100": ["BRCA1"],       # BRCA1 -> numeric key "1100"
        "200": ["GCNT2", "II"],  # GCNT2 -> numeric key "200"
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
    assert "hgnc:100" not in found, "IV should be filtered as complex numbering"

    # Text with actual gene name should match
    text_brca = "The BRCA1 gene is involved in DNA repair."
    hgnc_list2 = []
    found2 = _map_genes_in_text(text_brca, genedict1, hgnc_list2, genedict2)
    assert "hgnc:1100" in found2, "BRCA1 should be found with numeric ID"

    # GCNT2 alias "II" in complexes context should be filtered
    text_gcnt2 = "The respiratory chain complexes (I-V) are described."
    hgnc_list3 = []
    found3 = _map_genes_in_text(text_gcnt2, genedict1, hgnc_list3, genedict2)
    assert "hgnc:200" not in found3, "GCNT2 should be filtered in complexes context"


def test_map_genes_in_text_produces_numeric_hgnc_ids():
    """_map_genes_in_text with numeric-keyed dicts produces hgnc:NNNN format IDs."""
    genedict1 = {"1100": ["BRCA1"]}
    symbols = [" ", "(", ")", "[", "]", ",", "."]
    genedict2 = {"1100": []}
    for item in genedict1["1100"]:
        for s1 in symbols:
            for s2 in symbols:
                genedict2["1100"].append(s1 + item + s2)

    hgnc_list = []
    found = _map_genes_in_text(
        "The BRCA1 gene is important.", genedict1, hgnc_list, genedict2
    )
    assert found == ["hgnc:1100"], f"Expected ['hgnc:1100'], got {found}"
    assert hgnc_list == ["hgnc:1100"]


def test_map_genes_in_text_empty_input():
    """Edge case: empty text returns empty list."""
    result = _map_genes_in_text("", {"100": ["A"]}, [])
    assert result == []

    result2 = _map_genes_in_text("some text", {}, [])
    assert result2 == []


# ---------------------------------------------------------------------------
# Test: build_gene_xrefs (live BridgeDb) with symbol_lookup
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _bridgedb_reachable(),
    reason="BridgeDb API not reachable",
)
def test_build_gene_xrefs_live():
    """Test live BridgeDb xref resolution with numeric HGNC IDs and symbol_lookup."""
    # Numeric HGNC IDs: BRCA1=1100, TP53=11998
    test_genes = ["hgnc:1100", "hgnc:11998"]
    symbol_lookup = {"1100": "BRCA1", "11998": "TP53"}
    result = build_gene_xrefs(
        test_genes, BRIDGEDB_URL, timeout=30, symbol_lookup=symbol_lookup,
    )

    assert "geneiddict" in result
    assert "listofentrez" in result
    assert "listofensembl" in result
    assert "listofuniprot" in result

    # Known genes should have cross-references
    assert len(result["listofentrez"]) > 0, "Should find Entrez IDs"
    assert len(result["listofensembl"]) > 0, "Should find Ensembl IDs"
    assert len(result["listofuniprot"]) > 0, "Should find UniProt IDs"

    # geneiddict should have entries for our test genes (numeric IDs)
    assert "hgnc:1100" in result["geneiddict"]
    assert "hgnc:11998" in result["geneiddict"]
    assert len(result["geneiddict"]["hgnc:1100"]) > 0
