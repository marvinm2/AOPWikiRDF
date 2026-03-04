"""Tests for HGNC TSV parser genedict1/genedict2 output."""

import pytest

# Sample HGNC TSV with old header format ("Synonyms")
SAMPLE_TSV_OLD_HEADER = (
    "HGNC ID\tApproved symbol\tApproved name\tPrevious symbols\tSynonyms\t"
    "Accession numbers\tEnsembl ID(supplied by Ensembl)\n"
    "HGNC:5\tA1BG\talpha-1-B glycoprotein\t\tABG\tQ03154\tENSG00000121410\n"
    "HGNC:24086\tA1CF\tAPOBEC1 complementation factor\t\tACF, ASP, ACF64\tAF271790\tENSG00000148584\n"
    "HGNC:99999\tIGH@\timmunoglobulin heavy locus\t\t\t\tENSG00000211592\n"
    "HGNC:7\tA2M\talpha-2-macroglobulin\tFWP007\tCPAMD5\tBX647329, X68728\tENSG00000175899\n"
)

# Sample with new header format ("Alias symbols")
SAMPLE_TSV_NEW_HEADER = (
    "HGNC ID\tApproved symbol\tApproved name\tPrevious symbols\tAlias symbols\t"
    "Accession numbers\tEnsembl ID(supplied by Ensembl)\n"
    "HGNC:5\tA1BG\talpha-1-B glycoprotein\t\tABG\tQ03154\tENSG00000121410\n"
    "HGNC:7\tA2M\talpha-2-macroglobulin\tFWP007\tCPAMD5\tBX647329, X68728\tENSG00000175899\n"
)


class TestParserReturnType:
    """Test that parse_hgnc_genes returns the correct structure."""

    def test_returns_tuple_of_two_dicts(self):
        from aopwiki_rdf.hgnc.parser import parse_hgnc_genes

        result = parse_hgnc_genes(SAMPLE_TSV_OLD_HEADER)
        assert isinstance(result, tuple)
        assert len(result) == 2
        genedict1, genedict2 = result
        assert isinstance(genedict1, dict)
        assert isinstance(genedict2, dict)


class TestGenedict1Structure:
    """Test genedict1 keys and values."""

    def test_keys_are_gene_symbols(self):
        from aopwiki_rdf.hgnc.parser import parse_hgnc_genes

        genedict1, _ = parse_hgnc_genes(SAMPLE_TSV_OLD_HEADER)
        assert "A1BG" in genedict1
        assert "A1CF" in genedict1
        assert "A2M" in genedict1

    def test_values_contain_symbol_and_name(self):
        from aopwiki_rdf.hgnc.parser import parse_hgnc_genes

        genedict1, _ = parse_hgnc_genes(SAMPLE_TSV_OLD_HEADER)
        a1bg_vals = genedict1["A1BG"]
        assert "A1BG" in a1bg_vals
        assert "alpha-1-B glycoprotein" in a1bg_vals

    def test_values_contain_aliases(self):
        from aopwiki_rdf.hgnc.parser import parse_hgnc_genes

        genedict1, _ = parse_hgnc_genes(SAMPLE_TSV_OLD_HEADER)
        a1cf_vals = genedict1["A1CF"]
        assert "ACF" in a1cf_vals
        assert "ASP" in a1cf_vals
        assert "ACF64" in a1cf_vals

    def test_values_contain_previous_symbols(self):
        from aopwiki_rdf.hgnc.parser import parse_hgnc_genes

        genedict1, _ = parse_hgnc_genes(SAMPLE_TSV_OLD_HEADER)
        a2m_vals = genedict1["A2M"]
        assert "FWP007" in a2m_vals

    def test_values_contain_accession_and_ensembl(self):
        from aopwiki_rdf.hgnc.parser import parse_hgnc_genes

        genedict1, _ = parse_hgnc_genes(SAMPLE_TSV_OLD_HEADER)
        a2m_vals = genedict1["A2M"]
        # Accession numbers and Ensembl ID are in columns after aliases
        assert "BX647329" in a2m_vals or "X68728" in a2m_vals
        assert "ENSG00000175899" in a2m_vals


class TestGeneClusterFiltering:
    """Test that gene symbols containing '@' are filtered out."""

    def test_gene_clusters_filtered(self):
        from aopwiki_rdf.hgnc.parser import parse_hgnc_genes

        genedict1, genedict2 = parse_hgnc_genes(SAMPLE_TSV_OLD_HEADER)
        assert "IGH@" not in genedict1
        assert "IGH@" not in genedict2


class TestGenedict2PunctuationVariants:
    """Test genedict2 contains punctuation-delimited variants."""

    def test_contains_punctuation_variants(self):
        from aopwiki_rdf.hgnc.parser import parse_hgnc_genes

        _, genedict2 = parse_hgnc_genes(SAMPLE_TSV_OLD_HEADER)
        a1bg_variants = genedict2["A1BG"]
        # Should contain variants like " A1BG ", "(A1BG)", etc.
        assert " A1BG " in a1bg_variants
        assert "(A1BG)" in a1bg_variants
        assert "[A1BG]" in a1bg_variants
        assert ",A1BG," in a1bg_variants

    def test_variant_count_matches_symbols_squared(self):
        from aopwiki_rdf.hgnc.parser import parse_hgnc_genes

        genedict1, genedict2 = parse_hgnc_genes(SAMPLE_TSV_OLD_HEADER)
        # Each item in genedict1 generates 7*7=49 variants in genedict2
        symbols_count = 7  # [' ', '(', ')', '[', ']', ',', '.']
        for key in genedict1:
            expected = len(genedict1[key]) * symbols_count * symbols_count
            assert len(genedict2[key]) == expected


class TestHeaderHandling:
    """Test that parser handles both old and new header formats."""

    def test_old_header_synonyms(self):
        from aopwiki_rdf.hgnc.parser import parse_hgnc_genes

        genedict1, _ = parse_hgnc_genes(SAMPLE_TSV_OLD_HEADER)
        assert "A1BG" in genedict1

    def test_new_header_alias_symbols(self):
        from aopwiki_rdf.hgnc.parser import parse_hgnc_genes

        genedict1, _ = parse_hgnc_genes(SAMPLE_TSV_NEW_HEADER)
        assert "A1BG" in genedict1
        assert "A2M" in genedict1
