"""Phase B tests: BERN2 enrichment wired into the pipeline + genes writer.

Covers:
- map_ner_genes_in_kes  (KE-level NER mapper, mocked)
- _apply_bern2_enrichment  (pipeline union + provenance, mocked)
- write_genes_rdf  provenance predicates (flag on) vs legacy form (flag off)
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# map_ner_genes_in_kes
# ---------------------------------------------------------------------------

class TestMapNerGenesInKes:
    """KE-level BERN2 mapper -- iterates KE descriptions, returns HGNC sets."""

    def _config(self, tmp_path):
        from aopwiki_rdf.config import PipelineConfig
        return PipelineConfig(enable_bern2=True, ner_cache_dir=tmp_path)

    def test_returns_hgnc_uri_strings_keyed_by_ke(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import map_ner_genes_in_kes

        kedict = {
            "100": {"dc:description": "TP53 regulates apoptosis."},
            "101": {"dc:description": "A description with no genes."},
        }
        # find_hgnc_ids_via_ner_el returns numeric IDs; map_ner_genes_in_kes
        # formats them as hgnc:N to match the regex mapper convention.
        def fake_find(text, **kw):
            return {"11998"} if "TP53" in text else set()

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.find_hgnc_ids_via_ner_el",
            side_effect=fake_find,
        ):
            result = map_ner_genes_in_kes(kedict, self._config(tmp_path))

        assert result == {"100": {"hgnc:11998"}}
        assert "101" not in result  # KE with no hits is absent

    def test_skips_kes_without_description(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import map_ner_genes_in_kes

        kedict = {
            "100": {"dc:description": "TP53 here."},
            "102": {},  # no description
            "103": {"dc:description": ""},  # empty description
        }
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.find_hgnc_ids_via_ner_el",
            return_value={"11998"},
        ) as m:
            result = map_ner_genes_in_kes(kedict, self._config(tmp_path))

        # Only KE 100 has a usable description.
        assert set(result.keys()) == {"100"}
        assert m.call_count == 1

    def test_joins_list_valued_description(self, tmp_path):
        """dc:description can be a list of triple-quoted strings."""
        from aopwiki_rdf.mapping.ner_el_mapper import map_ner_genes_in_kes

        kedict = {
            "100": {"dc:description": ['"""First part."""', '"""TP53 part."""']},
        }
        captured = {}

        def fake_find(text, **kw):
            captured["text"] = text
            return {"11998"}

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.find_hgnc_ids_via_ner_el",
            side_effect=fake_find,
        ):
            result = map_ner_genes_in_kes(kedict, self._config(tmp_path))

        assert result == {"100": {"hgnc:11998"}}
        # Both list parts were joined into the text sent to BERN2.
        assert "First part" in captured["text"]
        assert "TP53 part" in captured["text"]

    def test_sleep_after_threads_through(self, tmp_path):
        """The cold-start politeness delay reaches find_hgnc_ids_via_ner_el."""
        from aopwiki_rdf.mapping.ner_el_mapper import map_ner_genes_in_kes

        kedict = {"100": {"dc:description": "TP53 here."}}
        captured = {}

        def fake_find(text, **kw):
            captured["sleep_after"] = kw.get("sleep_after")
            return set()

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.find_hgnc_ids_via_ner_el",
            side_effect=fake_find,
        ):
            map_ner_genes_in_kes(kedict, self._config(tmp_path), sleep_after=0.5)

        assert captured["sleep_after"] == 0.5

    def test_sleep_after_defaults_zero(self, tmp_path):
        """Production path uses no delay unless explicitly requested."""
        from aopwiki_rdf.mapping.ner_el_mapper import map_ner_genes_in_kes

        kedict = {"100": {"dc:description": "TP53 here."}}
        captured = {}

        def fake_find(text, **kw):
            captured["sleep_after"] = kw.get("sleep_after")
            return set()

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.find_hgnc_ids_via_ner_el",
            side_effect=fake_find,
        ):
            map_ner_genes_in_kes(kedict, self._config(tmp_path))

        assert captured["sleep_after"] == 0.0


# ---------------------------------------------------------------------------
# _apply_bern2_enrichment
# ---------------------------------------------------------------------------

class TestApplyBern2Enrichment:
    """Pipeline helper: union BERN2 genes + record provenance, mutate in place."""

    def test_unions_and_records_provenance(self, tmp_path):
        from aopwiki_rdf.config import PipelineConfig
        from aopwiki_rdf.pipeline import _apply_bern2_enrichment

        kedict = {
            "100": {"dc:identifier": "aop.events:100",
                    "edam:data_1025": ["hgnc:A", "hgnc:B"]},
            # KE 101 has no regex genes -- BERN2-only.
            "101": {"dc:identifier": "aop.events:101"},
        }
        kerdict = {
            "50": {"dc:identifier": "aop.relationships:50",
                   "edam:data_1025": ["hgnc:X"]},
        }
        gene_hgnclist = ["hgnc:A", "hgnc:B", "hgnc:X"]

        from aopwiki_rdf.mapping.ner_el_mapper import NerResult
        ner_results = {
            "100": NerResult({"hgnc:B", "hgnc:C"}),  # B overlaps, C is new
            "101": NerResult({"hgnc:D"}),            # BERN2-only KE
        }
        config = PipelineConfig(enable_bern2=True, ner_cache_dir=tmp_path)

        with patch(
            "aopwiki_rdf.pipeline.map_ner_genes_in_kes_result",
            return_value=ner_results,
        ):
            _apply_bern2_enrichment(kedict, kerdict, gene_hgnclist, config)

        # KE 100: union preserves regex order then appends NER-only sorted.
        assert kedict["100"]["edam:data_1025"] == ["hgnc:A", "hgnc:B", "hgnc:C"]
        assert kedict["100"]["_genes_regex"] == ["hgnc:A", "hgnc:B"]
        assert kedict["100"]["_genes_ner"] == ["hgnc:B", "hgnc:C"]

        # KE 101: BERN2-only -- edam:data_1025 set from nothing.
        assert kedict["101"]["edam:data_1025"] == ["hgnc:D"]
        assert kedict["101"]["_genes_regex"] == []
        assert kedict["101"]["_genes_ner"] == ["hgnc:D"]

        # KER 50: regex only, empty NER list.
        assert kerdict["50"]["_genes_regex"] == ["hgnc:X"]
        assert kerdict["50"]["_genes_ner"] == []

        # gene_hgnclist extended with new BERN2 IDs (C, D), no duplicates.
        assert "hgnc:C" in gene_hgnclist
        assert "hgnc:D" in gene_hgnclist
        assert gene_hgnclist.count("hgnc:B") == 1

    def test_ke_with_no_genes_untouched(self, tmp_path):
        from aopwiki_rdf.config import PipelineConfig
        from aopwiki_rdf.pipeline import _apply_bern2_enrichment

        kedict = {"200": {"dc:identifier": "aop.events:200"}}
        kerdict = {}
        gene_hgnclist = []

        with patch("aopwiki_rdf.pipeline.map_ner_genes_in_kes_result", return_value={}):
            _apply_bern2_enrichment(
                kedict, kerdict, gene_hgnclist,
                PipelineConfig(enable_bern2=True, ner_cache_dir=tmp_path),
            )

        # No regex, no NER -> KE stays bare, no provenance keys.
        assert "edam:data_1025" not in kedict["200"]
        assert "_genes_regex" not in kedict["200"]


# ---------------------------------------------------------------------------
# write_genes_rdf -- provenance predicates
# ---------------------------------------------------------------------------

def _gene_data(kedict, kerdict=None):
    """Minimal gene_data dict accepted by write_genes_rdf."""
    return {
        "kedict": kedict,
        "kerdict": kerdict or {},
        "hgnclist": [],
        "geneiddict": {},
        "listofentrez": [],
        "listofensembl": [],
        "listofuniprot": [],
        "symbol_lookup": {},
    }


class TestWriteGenesRdfProvenance:
    """Genes writer: legacy single-predicate form vs Phase B provenance form."""

    def test_flag_off_emits_legacy_single_predicate(self):
        from aopwiki_rdf.rdf.writer import write_genes_rdf

        kedict = {"100": {"dc:identifier": "aop.events:100",
                          "edam:data_1025": ["hgnc:11998", "hgnc:108"]}}
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "AOPWikiRDF-Genes.ttl")
            write_genes_rdf(out, _gene_data(kedict))  # config=None
            content = open(out).read()

        assert "aop.events:100\tedam:data_1025\thgnc:11998,hgnc:108 ." in content
        assert ":geneDetectedBy" not in content
        # No base ':' prefix line when the flag is off.
        assert "@prefix : <https://aopwiki.rdf" not in content

    def test_flag_on_emits_provenance_predicates(self):
        from aopwiki_rdf.rdf.writer import write_genes_rdf
        from aopwiki_rdf.config import PipelineConfig
        from rdflib import Graph

        kedict = {
            "100": {
                "dc:identifier": "aop.events:100",
                "edam:data_1025": ["hgnc:A", "hgnc:B", "hgnc:C"],
                "_genes_regex": ["hgnc:A", "hgnc:B"],
                "_genes_ner": ["hgnc:B", "hgnc:C"],
            }
        }
        config = PipelineConfig(enable_bern2=True)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "AOPWikiRDF-Genes.ttl")
            write_genes_rdf(out, _gene_data(kedict), config=config)
            content = open(out).read()
            Graph().parse(out, format="turtle")  # must be valid Turtle

        assert "@prefix : <https://aopwiki.rdf.bigcat-bioinformatics.org/>" in content
        assert "edam:data_1025\thgnc:A,hgnc:B,hgnc:C" in content
        assert ":geneDetectedByRegex\thgnc:A,hgnc:B" in content
        assert ":geneDetectedByNER\thgnc:B,hgnc:C" in content

    def test_flag_on_ker_omits_empty_ner_predicate(self):
        from aopwiki_rdf.rdf.writer import write_genes_rdf
        from aopwiki_rdf.config import PipelineConfig
        from rdflib import Graph

        kerdict = {
            "50": {
                "dc:identifier": "aop.relationships:50",
                "edam:data_1025": ["hgnc:X"],
                "_genes_regex": ["hgnc:X"],
                "_genes_ner": [],  # KERs are regex-only
            }
        }
        config = PipelineConfig(enable_bern2=True)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "AOPWikiRDF-Genes.ttl")
            write_genes_rdf(out, _gene_data({}, kerdict), config=config)
            content = open(out).read()
            Graph().parse(out, format="turtle")

        assert ":geneDetectedByRegex\thgnc:X" in content
        # Empty NER list -> no :geneDetectedByNER predicate emitted.
        assert ":geneDetectedByNER" not in content

    def test_flag_on_ke_with_only_ner_genes(self):
        """A KE regex missed entirely still emits a valid block."""
        from aopwiki_rdf.rdf.writer import write_genes_rdf
        from aopwiki_rdf.config import PipelineConfig
        from rdflib import Graph

        kedict = {
            "101": {
                "dc:identifier": "aop.events:101",
                "edam:data_1025": ["hgnc:D"],
                "_genes_regex": [],
                "_genes_ner": ["hgnc:D"],
            }
        }
        config = PipelineConfig(enable_bern2=True)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "AOPWikiRDF-Genes.ttl")
            write_genes_rdf(out, _gene_data(kedict), config=config)
            content = open(out).read()
            Graph().parse(out, format="turtle")

        assert "edam:data_1025\thgnc:D" in content
        assert ":geneDetectedByNER\thgnc:D" in content
        assert ":geneDetectedByRegex" not in content
