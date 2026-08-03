"""Tests for consolidating gene xrefs onto the shared BridgeDb client (#103).

The hazard being guarded is specific. BridgeDb's ``H`` system code is keyed by
gene SYMBOL, but this pipeline tracks genes by numeric HGNC ID. The shared
client previously keyed its results by whatever symbol came back, so swapping to
it naively would have returned ``hgnc:BRCA1`` where the consumer looks up
``hgnc:1100`` -- every cross-reference silently empty, every syntax check still
green. That is the same failure shape as PR #100 and the 2026-07-25 incident.
"""

from unittest.mock import MagicMock, patch

import pytest

from aopwiki_rdf.mapping.bridgedb import _rekey_to_original, batch_xrefs_gene
from aopwiki_rdf.mapping.gene_mapper import build_gene_xrefs

BATCH_RESPONSE = (
    "BRCA1\tHGNC Symbol\tL:672,En:ENSG00000012048,S:P38398\n"
    "TP53\tHGNC Symbol\tL:7157,En:ENSG00000141510,S:P04637\n"
)

SYMBOLS = {"1100": "BRCA1", "11998": "TP53"}
GENES = ["hgnc:1100", "hgnc:11998"]


def fake_post_factory(text):
    def fake_post(url, *args, **kwargs):
        resp = MagicMock()
        resp.text = text
        resp.raise_for_status.return_value = None
        return resp
    return fake_post


# --- Key shape: the whole point of the exercise ----------------------------

def test_results_are_keyed_by_the_caller_s_numeric_ids():
    with patch("aopwiki_rdf.mapping.bridgedb.requests.post",
               side_effect=fake_post_factory(BATCH_RESPONSE)):
        result = batch_xrefs_gene(GENES, "http://bridgedb/Human/",
                                  symbol_lookup=SYMBOLS)

    assert set(result) == {"hgnc:1100", "hgnc:11998"}, (
        f"must key by the numeric IDs the consumer looks up, got {set(result)}"
    )
    assert "hgnc:BRCA1" not in result


def test_symbols_are_what_gets_sent_to_the_service():
    """BridgeDb system code H resolves symbols; numeric IDs return nothing."""
    captured = {}

    def fake_post(url, *args, **kwargs):
        captured["data"] = kwargs.get("data", "")
        resp = MagicMock()
        resp.text = BATCH_RESPONSE
        resp.raise_for_status.return_value = None
        return resp

    with patch("aopwiki_rdf.mapping.bridgedb.requests.post", side_effect=fake_post):
        batch_xrefs_gene(GENES, "http://bridgedb/Human/", symbol_lookup=SYMBOLS)

    sent = captured["data"].split("\n")
    assert sent == ["BRCA1", "TP53"]
    assert "1100" not in sent


def test_xref_payload_survives_the_round_trip():
    with patch("aopwiki_rdf.mapping.bridgedb.requests.post",
               side_effect=fake_post_factory(BATCH_RESPONSE)):
        result = batch_xrefs_gene(GENES, "http://bridgedb/Human/",
                                  symbol_lookup=SYMBOLS)

    assert result["hgnc:1100"]["Entrez Gene"] == ["672"]
    assert result["hgnc:1100"]["Ensembl"] == ["ENSG00000012048"]
    assert result["hgnc:11998"]["Uniprot-TrEMBL"] == ["P04637"]


def test_symbol_keyed_callers_are_unaffected():
    """Without symbol_lookup the previous symbol-keyed behaviour is preserved."""
    with patch("aopwiki_rdf.mapping.bridgedb.requests.post",
               side_effect=fake_post_factory(BATCH_RESPONSE)):
        result = batch_xrefs_gene(["hgnc:BRCA1"], "http://bridgedb/Human/")

    assert "hgnc:BRCA1" in result


# --- Re-keying robustness --------------------------------------------------

def test_rekey_is_case_insensitive():
    """The service has been seen to echo identifiers with different casing."""
    out = _rekey_to_original({"hgnc:brca1": {"Ensembl": ["E1"]}},
                             {"hgnc:BRCA1": "hgnc:1100"})
    assert out == {"hgnc:1100": {"Ensembl": ["E1"]}}


def test_rekey_warns_rather_than_silently_dropping(caplog):
    """An unmappable response key must be visible, not quietly discarded."""
    out = _rekey_to_original({"hgnc:MYSTERY": {"Ensembl": ["E1"]}},
                             {"hgnc:BRCA1": "hgnc:1100"})
    assert "could not be mapped back" in caplog.text
    assert "hgnc:MYSTERY" in out  # retained, so nothing vanishes unnoticed


# --- The loud failure ------------------------------------------------------

def test_collapsed_resolution_rate_raises():
    """A 200-OK-but-unparseable response must stop the run at the cause.

    This is the shape of all three recorded incidents: BridgeDb returns
    something the parser does not understand, every gene resolves to {}, and
    nothing raises.
    """
    with patch("aopwiki_rdf.mapping.bridgedb.requests.post",
               side_effect=fake_post_factory("<html>gateway error</html>")):
        with pytest.raises(RuntimeError, match="resolved only"):
            build_gene_xrefs(GENES, "http://bridgedb/Human/",
                             symbol_lookup=SYMBOLS)


def test_healthy_rate_does_not_raise():
    with patch("aopwiki_rdf.mapping.bridgedb.requests.post",
               side_effect=fake_post_factory(BATCH_RESPONSE)):
        result = build_gene_xrefs(GENES, "http://bridgedb/Human/",
                                  symbol_lookup=SYMBOLS)

    assert result["geneiddict"]["hgnc:1100"] == [
        "ncbigene:672", "ensembl:ENSG00000012048", "uniprot:P38398",
    ]
    assert "ncbigene:7157" in result["listofentrez"]


def test_guard_can_be_disabled():
    """An explicit opt-out for the rare case where a low rate is expected."""
    with patch("aopwiki_rdf.mapping.bridgedb.requests.post",
               side_effect=fake_post_factory("")):
        result = build_gene_xrefs(GENES, "http://bridgedb/Human/",
                                  symbol_lookup=SYMBOLS, min_success_rate=0)

    assert result["geneiddict"] == {"hgnc:1100": [], "hgnc:11998": []}


def test_empty_gene_list_does_not_raise():
    """Zero genes is not a collapse -- there is nothing to resolve."""
    result = build_gene_xrefs([], "http://bridgedb/Human/", symbol_lookup={})
    assert result["geneiddict"] == {}
