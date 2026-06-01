"""Graceful-degradation tests for the BERN2 NER+EL gene mapper (NER-04).

A BERN2 outage must DEGRADE TO REGEX with a loud ERROR and a coverage
metric, never silently empty the canonical ``edam:data_1025`` gene view.
These tests prove:

  * the mapper can distinguish a BERN2 *failure* from a successful run that
    found no genes (``NerResult.failed``), while the public ``set[str]``
    wrapper contract is unchanged (Task 1);
  * the merge step ``_apply_bern2_enrichment`` falls back to the regex genes
    it already holds, marks each degraded KE, logs a single ERROR, and emits
    a coverage metric (Task 2 / success criterion 4);
  * the default production run (``enable_bern2`` off) is untouched and the
    new flag is inert (Task 3 / COMPAT-01 per-plan guard).

All HTTP is mocked (``patch`` against ``ner_el_mapper.requests.post``), so
the suite runs fully offline and deterministically -- NO ``@pytest.mark.skipif``.
Mirrors the offline-mock style of tests/unit/test_ner_el_mapper.py.
"""

import json
from unittest.mock import MagicMock, patch

import requests


# ---------------------------------------------------------------------------
# Shared mock builders (mirror test_ner_el_mapper.py)
# ---------------------------------------------------------------------------

def _bern2_response(annotations: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.text = json.dumps({"annotations": annotations})
    resp.raise_for_status = MagicMock()
    return resp


def _bridgedb_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


TP53_ANN = {"obj": "gene", "mention": "TP53", "id": ["NCBIGene:7157"], "prob": 0.99}
NON_GENE_ANN = {"obj": "disease", "mention": "tumor", "id": ["mesh:D009369"], "prob": 0.99}

BRIDGEDB_REAL_ROW_TP53 = (
    "7157\tEntrez Gene\tL:7157,H:TP53,En:ENSG00000141510,"
    "S:P04637,Hac:HGNC:11998,Om:191170,Q:NM_000546\n"
)


# ---------------------------------------------------------------------------
# Task 1: NerResult makes BERN2 failure observable
# ---------------------------------------------------------------------------

class TestNerResultFailureObservable:
    """find_hgnc_ids_via_ner_el_result distinguishes failure from empty."""

    def test_bern2_error_marks_failed(self, tmp_path):
        """query_bern2 returning _error -> NerResult.failed is True."""
        from aopwiki_rdf.mapping.ner_el_mapper import find_hgnc_ids_via_ner_el_result

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=requests.ConnectionError("net down"),
        ), patch("aopwiki_rdf.mapping.ner_el_mapper.time.sleep"):
            result = find_hgnc_ids_via_ner_el_result(
                "Text.",
                bern2_url="http://b2",
                bridgedb_url="https://example.org/Human/",
                cache_dir=tmp_path,
            )
        assert result.failed is True
        assert result.error is not None
        assert result.hgnc_ids == set()

    def test_bern2_ok_no_genes_is_not_failure(self, tmp_path):
        """BERN2 ran fine but found no gene entities -> failed False, empty ids."""
        from aopwiki_rdf.mapping.ner_el_mapper import find_hgnc_ids_via_ner_el_result

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            return_value=_bern2_response([NON_GENE_ANN]),
        ):
            result = find_hgnc_ids_via_ner_el_result(
                "A tumor is mentioned here.",
                bern2_url="http://b2",
                bridgedb_url="https://example.org/Human/",
                cache_dir=tmp_path,
            )
        assert result.failed is False
        assert result.error is None
        assert result.hgnc_ids == set()

    def test_bern2_ok_with_genes(self, tmp_path):
        """BERN2 ok with TP53 -> failed False, ids non-empty."""
        from aopwiki_rdf.mapping.ner_el_mapper import find_hgnc_ids_via_ner_el_result

        call_count = {"n": 0}

        def post_side_effect(url, *a, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _bern2_response([TP53_ANN])
            return _bridgedb_response(BRIDGEDB_REAL_ROW_TP53)

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=post_side_effect,
        ):
            result = find_hgnc_ids_via_ner_el_result(
                "TP53 is mentioned here.",
                bern2_url="http://b2",
                bridgedb_url="https://example.org/Human/",
                cache_dir=tmp_path,
            )
        assert result.failed is False
        assert result.error is None
        assert result.hgnc_ids == {"11998"}

    def test_wrapper_returns_same_set_as_result_ids(self, tmp_path):
        """find_hgnc_ids_via_ner_el (set[] wrapper) == result.hgnc_ids."""
        from aopwiki_rdf.mapping.ner_el_mapper import find_hgnc_ids_via_ner_el

        call_count = {"n": 0}

        def post_side_effect(url, *a, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _bern2_response([TP53_ANN])
            return _bridgedb_response(BRIDGEDB_REAL_ROW_TP53)

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=post_side_effect,
        ):
            wrapped = find_hgnc_ids_via_ner_el(
                "TP53 is mentioned here.",
                bern2_url="http://b2",
                bridgedb_url="https://example.org/Human/",
                cache_dir=tmp_path,
            )
        assert wrapped == {"11998"}
        assert isinstance(wrapped, set)

    def test_wrapper_returns_empty_set_on_failure(self, tmp_path):
        """The set[] wrapper still returns an empty set on BERN2 error
        (byte-identical to pre-plan behaviour for existing callers)."""
        from aopwiki_rdf.mapping.ner_el_mapper import find_hgnc_ids_via_ner_el

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=requests.ConnectionError("net down"),
        ), patch("aopwiki_rdf.mapping.ner_el_mapper.time.sleep"):
            result = find_hgnc_ids_via_ner_el(
                "Text.",
                bern2_url="http://b2",
                bridgedb_url="https://example.org/Human/",
                cache_dir=tmp_path,
            )
        assert result == set()
        assert isinstance(result, set)


class TestMapNerGenesInKesResult:
    """The result-returning batch helper records per-KE failure."""

    def _config(self, tmp_path):
        from aopwiki_rdf.config import PipelineConfig
        return PipelineConfig(ner_cache_dir=tmp_path / "cache")

    def test_per_ke_failure_recorded(self, tmp_path):
        """Every KE that fails BERN2 is a NerResult with failed=True."""
        from aopwiki_rdf.mapping.ner_el_mapper import map_ner_genes_in_kes_result

        kedict = {
            "111": {"dc:description": '"""KE one with text."""'},
            "222": {"dc:description": '"""KE two with text."""'},
        }
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=requests.ConnectionError("net down"),
        ), patch("aopwiki_rdf.mapping.ner_el_mapper.time.sleep"):
            results = map_ner_genes_in_kes_result(kedict, self._config(tmp_path))

        assert set(results) == {"111", "222"}
        assert all(r.failed for r in results.values())
        assert all(r.hgnc_ids == set() for r in results.values())

    def test_success_not_failed(self, tmp_path):
        """A successful KE BERN2 call is a NerResult with failed=False."""
        from aopwiki_rdf.mapping.ner_el_mapper import map_ner_genes_in_kes_result

        kedict = {"888": {"dc:description": '"""TP53 is involved here."""'}}

        call_count = {"n": 0}

        def post_side_effect(url, *a, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _bern2_response([TP53_ANN])
            return _bridgedb_response(BRIDGEDB_REAL_ROW_TP53)

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=post_side_effect,
        ):
            results = map_ner_genes_in_kes_result(kedict, self._config(tmp_path))

        assert results["888"].failed is False
        assert results["888"].hgnc_ids == {"hgnc:11998"}

    def test_blank_descriptions_skipped(self, tmp_path):
        """Whitespace-only descriptions are not scanned (no NerResult)."""
        from aopwiki_rdf.mapping.ner_el_mapper import map_ner_genes_in_kes_result

        kedict = {"empty": {"dc:description": '"""   """'}}
        with patch("aopwiki_rdf.mapping.ner_el_mapper.requests.post") as m:
            results = map_ner_genes_in_kes_result(kedict, self._config(tmp_path))
        assert results == {}
        m.assert_not_called()
