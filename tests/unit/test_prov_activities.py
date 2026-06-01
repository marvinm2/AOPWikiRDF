"""Phase 7 (07-03) tests: PROV-O activity layer + machine-readable primacy.

Covers the gated genes-file provenance activity block emitted by
``write_genes_rdf`` when ``enable_bern2=True`` (D-01/02/03/07):

- flag-on: two ``prov:Activity`` resources declared once in the header, BERN2
  marked ``:isFeaturedMethod true`` with ``:minConfidence "0.70"^^xsd:decimal``,
  predicate-level ``prov:wasGeneratedBy`` links, and valid Turtle;
- flag-off: NONE of the prov/primacy/confidence triples appear;
- no-per-subject: no ``prov:`` predicate on any KE/KER subject (activity-level
  provenance only -- D-01).

Mirrors ``TestWriteGenesRdfProvenance`` in ``tests/unit/test_bern2_pipeline.py``.
Fully offline; no network, no skipif.
"""

import os
import tempfile

import pytest

from rdflib import Graph
from rdflib.namespace import Namespace


PROV = Namespace("http://www.w3.org/ns/prov#")


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


def _kedict_with_both_methods():
    """A KE whose gene block emits both :geneDetectedByRegex and :geneDetectedByNER."""
    return {
        "100": {
            "dc:identifier": "aop.events:100",
            "edam:data_1025": ["hgnc:A", "hgnc:B", "hgnc:C"],
            "_genes_regex": ["hgnc:A", "hgnc:B"],
            "_genes_ner": ["hgnc:B", "hgnc:C"],
        }
    }


def _kerdict_with_regex():
    """A KER whose gene block emits :geneDetectedByRegex (KERs may carry NER too)."""
    return {
        "50": {
            "dc:identifier": "aop.relationships:50",
            "edam:data_1025": ["hgnc:X", "hgnc:Y"],
            "_genes_regex": ["hgnc:X"],
            "_genes_ner": ["hgnc:Y"],
        }
    }


def _write_flag_on(kedict, kerdict):
    """Write a flag-on genes file and return (content, path-in-tempdir-reader)."""
    from aopwiki_rdf.rdf.writer import write_genes_rdf
    from aopwiki_rdf.config import PipelineConfig

    config = PipelineConfig(enable_bern2=True)
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "AOPWikiRDF-Genes.ttl")
    write_genes_rdf(out, _gene_data(kedict, kerdict), config=config)
    with open(out) as fh:
        content = fh.read()
    return content, out


class TestProvActivitiesFlagOn:
    """Flag-on emits the activity block, primacy flag, confidence policy, links."""

    def test_activities_primacy_confidence_and_links_present(self):
        content, out = _write_flag_on(_kedict_with_both_methods(), {})

        # Valid Turtle.
        Graph().parse(out, format="turtle")

        assert ":BERN2NERMapping a prov:Activity" in content
        assert ":isFeaturedMethod true" in content
        assert ':minConfidence "0.70"^^xsd:decimal' in content
        assert ":RegexGeneMapping a prov:Activity" in content
        assert ":isFeaturedMethod false" in content
        assert ":geneDetectedByNER prov:wasGeneratedBy :BERN2NERMapping" in content
        assert ":geneDetectedByRegex prov:wasGeneratedBy :RegexGeneMapping" in content

    def test_canonical_method_discoverable_via_sparql(self):
        """A consumer finds the featured (BERN2) method from the RDF alone."""
        content, out = _write_flag_on(_kedict_with_both_methods(), {})
        g = Graph()
        g.parse(out, format="turtle")

        BASE = Namespace("https://aopwiki.rdf.bigcat-bioinformatics.org/")
        rows = list(
            g.query(
                """
                SELECT ?act WHERE {
                    ?act a prov:Activity ;
                         :isFeaturedMethod true .
                    ?pred prov:wasGeneratedBy ?act .
                }
                """,
                initNs={"prov": PROV, "": BASE},
            )
        )
        featured = {str(r.act) for r in rows}
        assert str(BASE.BERN2NERMapping) in featured
        assert str(BASE.RegexGeneMapping) not in featured

    def test_min_confidence_is_a_decimal_literal(self):
        """The 0.70 threshold is asserted as a machine-readable decimal, not a string."""
        _, out = _write_flag_on(_kedict_with_both_methods(), {})
        g = Graph()
        g.parse(out, format="turtle")
        BASE = Namespace("https://aopwiki.rdf.bigcat-bioinformatics.org/")
        vals = list(
            g.objects(BASE.BERN2NERMapping, BASE.minConfidence)
        )
        assert len(vals) == 1
        # rdflib coerces xsd:decimal to a Decimal-typed Literal.
        assert float(vals[0]) == pytest.approx(0.70)


class TestProvActivitiesFlagOff:
    """Flag-off emits NONE of the new prov / primacy / confidence triples."""

    def test_no_prov_or_primacy_or_confidence_when_off(self):
        from aopwiki_rdf.rdf.writer import write_genes_rdf

        kedict = {
            "100": {
                "dc:identifier": "aop.events:100",
                "edam:data_1025": ["hgnc:A", "hgnc:B"],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "AOPWikiRDF-Genes.ttl")
            write_genes_rdf(out, _gene_data(kedict))  # config=None -> flag off
            content = open(out).read()

        assert "prov:Activity" not in content
        assert ":isFeaturedMethod" not in content
        assert ":minConfidence" not in content
        assert "prov:wasGeneratedBy" not in content
        assert "@prefix prov:" not in content


class TestNoPerSubjectProvenance:
    """D-01: provenance is activity-level only -- no prov:* on KE/KER subjects."""

    def test_no_prov_predicate_on_ke_or_ker_subjects(self):
        content, out = _write_flag_on(
            _kedict_with_both_methods(), _kerdict_with_regex()
        )
        g = Graph()
        g.parse(out, format="turtle")

        AOP_EVENTS = "https://identifiers.org/aop.events/"
        AOP_RELS = "https://identifiers.org/aop.relationships/"

        for s, p, _o in g:
            subj = str(s)
            if subj.startswith(AOP_EVENTS) or subj.startswith(AOP_RELS):
                assert not str(p).startswith(str(PROV)), (
                    f"unexpected prov triple on subject {subj}: {p}"
                )
