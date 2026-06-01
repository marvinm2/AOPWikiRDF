"""Integration test for KER NER union wiring (D-08), flag-on, fully offline.

Mirrors the flag-on genes-write + rdflib re-parse pattern in
tests/unit/test_bern2_pipeline.py, but for the KER branch of
``_apply_bern2_enrichment``: with a mocked BERN2 KER mapper returning a gene
for a KER, running the union build + genes writer must

  * make each KER's ``edam:data_1025`` a superset of its regex genes
    (``_genes_regex``) — the union is never thinner than regex;
  * populate ``_genes_ner`` so the writer emits ``:geneDetectedByNER`` on the
    KER subject where NER hit;
  * degrade a KER to regex (NerResult.failed) rather than contribute empty NER
    silently;
  * produce valid Turtle (rdflib parses the output).

All BERN2/HTTP is mocked via the result-returning KER mapper, so the suite is
deterministic and needs no network — no skipif.
"""

import os
import tempfile
from unittest.mock import patch

import pytest


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


class TestKerNerUnionWiring:
    """_apply_bern2_enrichment KER branch builds the regex union NER union."""

    def _config(self, tmp_path):
        from aopwiki_rdf.config import PipelineConfig
        return PipelineConfig(enable_bern2=True, ner_cache_dir=tmp_path)

    def test_ker_union_superset_of_regex_and_ner_on_subject(self, tmp_path):
        from aopwiki_rdf.pipeline import _apply_bern2_enrichment
        from aopwiki_rdf.mapping.ner_el_mapper import NerResult
        from aopwiki_rdf.rdf.writer import write_genes_rdf
        from rdflib import Graph

        kedict = {}
        kerdict = {
            "50": {
                "dc:identifier": "aop.relationships:50",
                "edam:data_1025": ["hgnc:X"],
            },
            # KER 51 has no regex genes -- BERN2-only contribution.
            "51": {"dc:identifier": "aop.relationships:51"},
        }
        gene_hgnclist = ["hgnc:X"]

        # Mocked KER NER: KER 50 gains a new NER gene (Y), KER 51 is NER-only (Z).
        ker_ner_results = {
            "50": NerResult({"hgnc:Y"}),
            "51": NerResult({"hgnc:Z"}),
        }
        config = self._config(tmp_path)

        with patch(
            "aopwiki_rdf.pipeline.map_ner_genes_in_kers_result",
            return_value=ker_ner_results,
        ):
            _apply_bern2_enrichment(kedict, kerdict, gene_hgnclist, config)

        # KER 50: union >= regex; NER gene appended.
        assert set(kerdict["50"]["edam:data_1025"]) >= set(kerdict["50"]["_genes_regex"])
        assert kerdict["50"]["_genes_regex"] == ["hgnc:X"]
        assert kerdict["50"]["_genes_ner"] == ["hgnc:Y"]
        assert kerdict["50"]["edam:data_1025"] == ["hgnc:X", "hgnc:Y"]

        # KER 51: BERN2-only.
        assert kerdict["51"]["edam:data_1025"] == ["hgnc:Z"]
        assert kerdict["51"]["_genes_regex"] == []
        assert kerdict["51"]["_genes_ner"] == ["hgnc:Z"]

        # gene_hgnclist extended with the NER-only IDs.
        assert "hgnc:Y" in gene_hgnclist
        assert "hgnc:Z" in gene_hgnclist

        # Genes writer emits :geneDetectedByNER on KER subjects where NER hit.
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "AOPWikiRDF-Genes.ttl")
            write_genes_rdf(out, _gene_data(kedict, kerdict), config=config)
            content = open(out).read()
            Graph().parse(out, format="turtle")  # must be valid Turtle

        assert "aop.relationships:50\tedam:data_1025\thgnc:X,hgnc:Y" in content
        assert ":geneDetectedByNER\thgnc:Y" in content
        assert ":geneDetectedByNER\thgnc:Z" in content

    def test_ker_bern2_outage_degrades_to_regex(self, tmp_path):
        """A failed KER NerResult keeps the regex genes, contributes no NER."""
        from aopwiki_rdf.pipeline import _apply_bern2_enrichment
        from aopwiki_rdf.mapping.ner_el_mapper import NerResult

        kedict = {}
        kerdict = {
            "60": {
                "dc:identifier": "aop.relationships:60",
                "edam:data_1025": ["hgnc:R"],
            },
        }
        gene_hgnclist = ["hgnc:R"]
        ker_ner_results = {
            "60": NerResult(set(), failed=True, error="BERN2 unreachable"),
        }
        config = self._config(tmp_path)

        with patch(
            "aopwiki_rdf.pipeline.map_ner_genes_in_kers_result",
            return_value=ker_ner_results,
        ):
            _apply_bern2_enrichment(kedict, kerdict, gene_hgnclist, config)

        # Regex genes preserved (>= regex baseline); no NER contributed.
        assert kerdict["60"]["edam:data_1025"] == ["hgnc:R"]
        assert kerdict["60"]["_genes_regex"] == ["hgnc:R"]
        assert kerdict["60"]["_genes_ner"] == []
