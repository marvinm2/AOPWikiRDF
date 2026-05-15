"""Unit tests for the BERN2 NER+EL gene mapper.

Mocks the BERN2 and BridgeDb HTTP calls so the tests run offline and
deterministically. Mirrors the mocking pattern used in
tests/unit/test_hgnc_download.py (``unittest.mock.patch`` against the
``requests`` module imported by the module under test).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures: mock BERN2 / BridgeDb responses
# ---------------------------------------------------------------------------

def _bern2_response(annotations: list[dict]) -> MagicMock:
    """Build a MagicMock that mimics requests.Response.json()."""
    resp = MagicMock()
    resp.json = MagicMock(return_value={"annotations": annotations})
    resp.raise_for_status = MagicMock()
    return resp


def _bridgedb_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


# Two genes from the spike: TP53 (NCBIGene:7157 -> HGNC:11998) and
# ACHE (NCBIGene:43 -> HGNC:108).
TP53_ANN = {
    "obj": "gene",
    "mention": "TP53",
    "id": ["NCBIGene:7157"],
    "prob": 0.99,
}
ACHE_ANN = {
    "obj": "gene",
    "mention": "acetylcholinesterase",
    "id": ["NCBIGene:43"],
    "prob": 0.95,
}
NON_GENE_ANN = {
    "obj": "disease",
    "mention": "tumor",
    "id": ["mesh:D009369"],
    "prob": 0.99,
}
CUI_LESS_ANN = {
    "obj": "gene",
    "mention": "something",
    "id": ["CUI-less"],
    "prob": 0.6,
}

BRIDGEDB_REAL_ROW_TP53 = (
    "7157\tEntrez Gene\tL:7157,H:TP53,En:ENSG00000141510,"
    "S:P04637,Hac:HGNC:11998,Om:191170,Q:NM_000546\n"
)
BRIDGEDB_REAL_ROW_ACHE = (
    "43\tEntrez Gene\tL:43,H:ACHE,En:ENSG00000087085,"
    "Hac:HGNC:108,S:P22303\n"
)


# ---------------------------------------------------------------------------
# extract_ncbi_gene_ids
# ---------------------------------------------------------------------------

class TestExtractNcbiGeneIds:
    """Extract NCBI Gene IDs from a BERN2 response payload."""

    def test_extracts_ncbigene_prefix(self):
        from aopwiki_rdf.mapping.ner_el_mapper import extract_ncbi_gene_ids
        result = extract_ncbi_gene_ids({"annotations": [TP53_ANN, ACHE_ANN]})
        assert result == {"7157", "43"}

    def test_skips_non_gene_obj_types(self):
        from aopwiki_rdf.mapping.ner_el_mapper import extract_ncbi_gene_ids
        result = extract_ncbi_gene_ids({"annotations": [TP53_ANN, NON_GENE_ANN]})
        assert result == {"7157"}

    def test_skips_cui_less_identifiers(self):
        from aopwiki_rdf.mapping.ner_el_mapper import extract_ncbi_gene_ids
        result = extract_ncbi_gene_ids({"annotations": [TP53_ANN, CUI_LESS_ANN]})
        assert result == {"7157"}

    def test_accepts_entrezgene_prefix_alias(self):
        from aopwiki_rdf.mapping.ner_el_mapper import extract_ncbi_gene_ids
        ann = {"obj": "gene", "mention": "X", "id": ["EntrezGene:7157"]}
        result = extract_ncbi_gene_ids({"annotations": [ann]})
        assert result == {"7157"}

    def test_empty_response(self):
        from aopwiki_rdf.mapping.ner_el_mapper import extract_ncbi_gene_ids
        assert extract_ncbi_gene_ids({}) == set()
        assert extract_ncbi_gene_ids({"annotations": []}) == set()
        assert extract_ncbi_gene_ids({"annotations": None}) == set()


# ---------------------------------------------------------------------------
# map_ncbi_to_hgnc -- via BridgeDb
# ---------------------------------------------------------------------------

class TestMapNcbiToHgnc:
    """NCBI Gene -> HGNC numeric ID via BridgeDb batch API."""

    def test_parses_hac_hgnc_token(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import map_ncbi_to_hgnc
        mock_resp = _bridgedb_response(
            BRIDGEDB_REAL_ROW_TP53 + BRIDGEDB_REAL_ROW_ACHE
        )
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            return_value=mock_resp,
        ):
            out = map_ncbi_to_hgnc(
                {"7157", "43"},
                bridgedb_url="https://example.org/Human/",
                cache_dir=tmp_path,
            )
        assert out == {"7157": "11998", "43": "108"}

    def test_ignores_h_symbol_token(self, tmp_path):
        """Bare ``H:`` carries the symbol, not the numeric HGNC ID."""
        from aopwiki_rdf.mapping.ner_el_mapper import map_ncbi_to_hgnc
        # No Hac: token here -- only H:SYMBOL. Should not map.
        mock_resp = _bridgedb_response("7157\tEntrez Gene\tL:7157,H:TP53,En:ENSG00000141510\n")
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            return_value=mock_resp,
        ):
            out = map_ncbi_to_hgnc(
                {"7157"},
                bridgedb_url="https://example.org/Human/",
                cache_dir=tmp_path,
            )
        assert out == {}

    def test_handles_na_response(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import map_ncbi_to_hgnc
        mock_resp = _bridgedb_response("9999999\tEntrez Gene\tN/A\n")
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            return_value=mock_resp,
        ):
            out = map_ncbi_to_hgnc(
                {"9999999"},
                bridgedb_url="https://example.org/Human/",
                cache_dir=tmp_path,
            )
        assert out == {}

    def test_skips_non_numeric_input(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import map_ncbi_to_hgnc
        with patch("aopwiki_rdf.mapping.ner_el_mapper.requests.post") as m:
            out = map_ncbi_to_hgnc(
                {"abc", "NCBIGene:7157", ""},  # all should be filtered out
                bridgedb_url="https://example.org/Human/",
                cache_dir=tmp_path,
            )
        m.assert_not_called()
        assert out == {}

    def test_uses_cache_on_second_call(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import map_ncbi_to_hgnc
        mock_resp = _bridgedb_response(BRIDGEDB_REAL_ROW_TP53)
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            return_value=mock_resp,
        ) as m:
            out1 = map_ncbi_to_hgnc({"7157"}, "https://example.org/Human/", tmp_path)
            out2 = map_ncbi_to_hgnc({"7157"}, "https://example.org/Human/", tmp_path)
        assert out1 == out2 == {"7157": "11998"}
        assert m.call_count == 1, "Second call should hit the disk cache"

    def test_network_failure_logs_warning(self, tmp_path, caplog):
        from aopwiki_rdf.mapping.ner_el_mapper import map_ncbi_to_hgnc
        import requests
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=requests.ConnectionError("simulated"),
        ):
            with caplog.at_level("WARNING"):
                out = map_ncbi_to_hgnc(
                    {"7157"}, "https://example.org/Human/", tmp_path,
                )
        assert out == {}
        assert any("BridgeDb batch failed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# query_bern2 -- BERN2 single + chunking fallback
# ---------------------------------------------------------------------------

class TestQueryBern2:
    """BERN2 hosted-API client + chunking fallback."""

    def test_caches_successful_response(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import query_bern2
        mock_resp = _bern2_response([TP53_ANN])
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            return_value=mock_resp,
        ) as m:
            r1 = query_bern2("TP53 is a tumor suppressor.", "http://b2", tmp_path)
            r2 = query_bern2("TP53 is a tumor suppressor.", "http://b2", tmp_path)
        assert r1 == r2
        assert len(r1["annotations"]) == 1
        assert m.call_count == 1, "Cache should serve the second call"

    def test_chunking_fallback_on_truncated_json(self, tmp_path):
        """When a single call raises JSONDecodeError, the fallback chunks
        the text by sentences and merges sub-responses."""
        from aopwiki_rdf.mapping.ner_el_mapper import query_bern2

        # First call: simulate truncated JSON. Subsequent (chunked) calls
        # return clean responses, one each.
        good_resp_1 = _bern2_response([TP53_ANN])
        good_resp_2 = _bern2_response([ACHE_ANN])
        truncated = MagicMock()
        truncated.raise_for_status = MagicMock()
        truncated.json = MagicMock(
            side_effect=json.JSONDecodeError("truncated", "doc", 0)
        )

        sequence = iter([truncated, good_resp_1, good_resp_2])
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=lambda *a, **kw: next(sequence),
        ):
            # Build text long enough to force two-chunk split (> 1500 chars).
            # The chunking fallback splits by sentence boundary.
            sentence_a = "TP53 is a tumor suppressor gene. " + ("filler " * 200)
            sentence_b = ("Acetylcholinesterase is an enzyme. "
                          + ("more filler " * 200))
            text = sentence_a + sentence_b
            result = query_bern2(text, "http://b2", tmp_path)

        mentions = {a["mention"] for a in result["annotations"]}
        assert "TP53" in mentions
        assert "acetylcholinesterase" in mentions

    def test_records_error_when_all_attempts_fail(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import query_bern2
        import requests

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=requests.ConnectionError("net down"),
        ):
            result = query_bern2("Any text.", "http://b2", tmp_path)

        assert "_error" in result

    def test_corrupt_cache_is_replaced(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import query_bern2, _cache_key
        text = "TP53"
        cache_dir = tmp_path
        # Pre-populate cache with invalid JSON.
        cache_path = cache_dir / f"{_cache_key(text)}.json"
        cache_path.write_text("not valid json {{{", encoding="utf-8")

        mock_resp = _bern2_response([TP53_ANN])
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            return_value=mock_resp,
        ):
            result = query_bern2(text, "http://b2", cache_dir)
        assert result["annotations"][0]["mention"] == "TP53"
        # Cache should now contain valid JSON.
        assert json.loads(cache_path.read_text())["annotations"][0]["mention"] == "TP53"


# ---------------------------------------------------------------------------
# find_hgnc_ids_via_ner_el -- end-to-end (still mocked)
# ---------------------------------------------------------------------------

class TestFindHgncIdsViaNerEl:
    """End-to-end composition: BERN2 -> NCBI extraction -> BridgeDb -> HGNC set."""

    def test_full_pipeline_returns_hgnc_ids(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import find_hgnc_ids_via_ner_el

        bern2_call = _bern2_response([TP53_ANN, ACHE_ANN])
        bridgedb_call = _bridgedb_response(
            BRIDGEDB_REAL_ROW_TP53 + BRIDGEDB_REAL_ROW_ACHE
        )

        # First call to requests.post = BERN2; second = BridgeDb.
        call_count = {"n": 0}

        def post_side_effect(url, *a, **kw):
            call_count["n"] += 1
            return bern2_call if call_count["n"] == 1 else bridgedb_call

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=post_side_effect,
        ):
            result = find_hgnc_ids_via_ner_el(
                "TP53 and acetylcholinesterase are mentioned here.",
                bern2_url="http://b2",
                bridgedb_url="https://example.org/Human/",
                cache_dir=tmp_path,
            )

        assert result == {"11998", "108"}

    def test_returns_empty_when_bern2_errors(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import find_hgnc_ids_via_ner_el
        import requests

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=requests.ConnectionError("net down"),
        ):
            result = find_hgnc_ids_via_ner_el(
                "Text.",
                bern2_url="http://b2",
                bridgedb_url="https://example.org/Human/",
                cache_dir=tmp_path,
            )
        assert result == set()

    def test_returns_empty_when_no_gene_entities(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import find_hgnc_ids_via_ner_el

        mock_resp = _bern2_response([NON_GENE_ANN])
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            return_value=mock_resp,
        ) as m:
            result = find_hgnc_ids_via_ner_el(
                "A tumor is mentioned here.",
                bern2_url="http://b2",
                bridgedb_url="https://example.org/Human/",
                cache_dir=tmp_path,
            )
        # BERN2 was called but BridgeDb was not (no NCBI IDs to map).
        assert result == set()
        assert m.call_count == 1


# ---------------------------------------------------------------------------
# PipelineConfig wiring (Phase A flag defaults)
# ---------------------------------------------------------------------------

class TestPipelineConfigFields:
    """Phase A adds BERN2 fields to PipelineConfig with default-off flag."""

    def test_enable_bern2_defaults_false(self):
        from aopwiki_rdf.config import PipelineConfig
        assert PipelineConfig().enable_bern2 is False

    def test_bern2_url_default_is_hosted_api(self):
        from aopwiki_rdf.config import PipelineConfig
        assert "bern2.korea.ac.kr" in PipelineConfig().bern2_url

    def test_ner_cache_dir_default_under_data(self):
        from aopwiki_rdf.config import PipelineConfig
        assert PipelineConfig().ner_cache_dir == Path("data/cache/bern2/")

    def test_string_ner_cache_dir_coerced_to_path(self):
        from aopwiki_rdf.config import PipelineConfig
        cfg = PipelineConfig(ner_cache_dir="my/cache")
        assert isinstance(cfg.ner_cache_dir, Path)
