"""Partial-chunk cache-integrity tests for the BERN2 NER+EL mapper (D-11).

When ``query_bern2`` chunks a long description (JSON-truncation fallback) and
some chunks succeed while others error, the merged result must NOT be cached as
a complete success. It is cached with a ``_partial`` marker so that:

  * ``is_cached`` reports it as a MISS (the failed chunk is re-warmable);
  * the ``query_bern2`` cache-read short-circuit re-issues the failed chunk on
    the next run rather than replaying the incomplete cache;
  * the genes that *were* found are kept (additive) and ``_partial`` composes
    with ``NerResult`` as ``failed=False`` -- it never trips the regex-only
    degradation path (only an all-fail ``_error`` does).

All HTTP is mocked (``patch`` against ``ner_el_mapper.requests.post``), so the
suite is fully offline and deterministic -- NO ``@pytest.mark.skipif``. Mirrors
the offline-mock structure of tests/unit/test_ner_graceful_degradation.py.

Cache-key/layout note: ``query_bern2`` writes to ``{cache_dir}/{key}.json`` while
``is_cached`` and ``find_hgnc_ids_via_ner_el_result`` look under
``{ner_cache_dir}/bern2/{key}.json``. So these tests pass ``ner_cache_dir/"bern2"``
as the ``query_bern2`` cache dir and ``ner_cache_dir`` to ``is_cached`` so both
gates resolve to the same file.
"""

import json
from unittest.mock import MagicMock, patch

import requests

from aopwiki_rdf.mapping.ner_el_mapper import (
    _cache_key,
    find_hgnc_ids_via_ner_el_result,
    is_cached,
    query_bern2,
)


# ---------------------------------------------------------------------------
# Shared mock builders (mirror test_ner_graceful_degradation.py)
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

BRIDGEDB_REAL_ROW_TP53 = (
    "7157\tEntrez Gene\tL:7157,H:TP53,En:ENSG00000141510,"
    "S:P04637,Hac:HGNC:11998,Om:191170,Q:NM_000546\n"
)

# Force the chunking branch: text well over _BERN2_CHUNK_CHARS (1500), built
# from two clearly sentence-bounded halves so re.split keeps them in distinct
# chunks. Each half is padded past the chunk size so they never coalesce.
_CHUNK1 = "TP53 is mentioned in this first sentence. " + ("Filler word here. " * 120)
_CHUNK2 = "A second distinct sentence follows now. " + ("More filler text here. " * 120)
MIXED_TEXT = _CHUNK1 + _CHUNK2


def _read_cache(ner_cache_dir, text) -> dict:
    path = ner_cache_dir / "bern2" / f"{_cache_key(text)}.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Mixed-chunk outcome -> _partial marker, miss, retry
# ---------------------------------------------------------------------------

class TestPartialChunkCache:
    """A mixed success/error chunk run is cached _partial, not complete."""

    def _mixed_post(self):
        """Branch on the POSTed text, not a call counter.

        ``_bern2_post`` retries up to 3 times per logical call, so a global
        counter does not align with chunk boundaries. We key off the text:

          * the full ``MIXED_TEXT`` (initial single-call attempt) -> error,
            which forces the sentence-bounded chunking fallback;
          * any chunk containing the chunk-1 marker -> success with TP53;
          * any other chunk (chunk 2) -> error.
        """
        def side_effect(url, *a, **kw):
            sent = (kw.get("json") or {}).get("text", "")
            if sent == MIXED_TEXT:
                # Initial single-call attempt: error -> triggers chunking.
                raise requests.ConnectionError("force chunking")
            if "first sentence" in sent:
                # Chunk 1 carries TP53.
                return _bern2_response([TP53_ANN])
            # Chunk 2 (and any retries of it): error.
            raise requests.ConnectionError("chunk 2 down")

        return side_effect, {}

    def test_mixed_chunk_writes_partial_marker(self, tmp_path):
        """Test 1: cache JSON has _partial true AND keeps chunk-1 annotations."""
        bern2_dir = tmp_path / "bern2"
        side_effect, _ = self._mixed_post()
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=side_effect,
        ), patch("aopwiki_rdf.mapping.ner_el_mapper.time.sleep"):
            result = query_bern2(MIXED_TEXT, bern2_url="http://b2", cache_dir=bern2_dir)

        assert result.get("_partial") is True
        assert result.get("annotations"), "partial result must keep found genes"
        assert any(a.get("mention") == "TP53" for a in result["annotations"])

        cached = _read_cache(tmp_path, MIXED_TEXT)
        assert cached.get("_partial") is True
        assert cached.get("annotations")
        assert any(a.get("mention") == "TP53" for a in cached["annotations"])

    def test_partial_is_cache_miss(self, tmp_path):
        """Test 2: is_cached returns False for a _partial entry."""
        bern2_dir = tmp_path / "bern2"
        side_effect, _ = self._mixed_post()
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=side_effect,
        ), patch("aopwiki_rdf.mapping.ner_el_mapper.time.sleep"):
            query_bern2(MIXED_TEXT, bern2_url="http://b2", cache_dir=bern2_dir)

        assert is_cached(MIXED_TEXT, tmp_path) is False

    def test_partial_is_retried_on_second_call(self, tmp_path):
        """Test 3: a second query_bern2 re-issues the failed chunk (no replay)."""
        bern2_dir = tmp_path / "bern2"

        # First call: chunk 1 ok, chunk 2 down -> _partial cached.
        side_effect, _ = self._mixed_post()
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=side_effect,
        ), patch("aopwiki_rdf.mapping.ner_el_mapper.time.sleep"):
            query_bern2(MIXED_TEXT, bern2_url="http://b2", cache_dir=bern2_dir)

        # Second call: everything succeeds now. If the short-circuit replayed
        # the _partial cache, requests.post would never be called.
        call_log = {"n": 0}

        def all_ok(url, *a, **kw):
            call_log["n"] += 1
            return _bern2_response([TP53_ANN])

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=all_ok,
        ), patch("aopwiki_rdf.mapping.ner_el_mapper.time.sleep"):
            result = query_bern2(MIXED_TEXT, bern2_url="http://b2", cache_dir=bern2_dir)

        assert call_log["n"] > 0, "second call must re-issue, not replay _partial"
        # And the re-warmed entry is now a complete success.
        assert result.get("_partial") is not True
        assert is_cached(MIXED_TEXT, tmp_path) is True

    def test_partial_composes_with_ner_result(self, tmp_path):
        """Test 4: find_hgnc_ids_via_ner_el_result over a _partial returns
        failed=False and includes the gene(s) that succeeded (additive)."""
        def side_effect(url, *a, **kw):
            if "json" not in kw:
                # BridgeDb reverse-map call (uses data=, not json=).
                return _bridgedb_response(BRIDGEDB_REAL_ROW_TP53)
            sent = (kw.get("json") or {}).get("text", "")
            if sent == MIXED_TEXT:
                # Initial single-call attempt: error -> chunking.
                raise requests.ConnectionError("force chunking")
            if "first sentence" in sent:
                # Chunk 1: TP53 gene.
                return _bern2_response([TP53_ANN])
            # Chunk 2: error.
            raise requests.ConnectionError("chunk 2 down")

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=side_effect,
        ), patch("aopwiki_rdf.mapping.ner_el_mapper.time.sleep"):
            result = find_hgnc_ids_via_ner_el_result(
                MIXED_TEXT,
                bern2_url="http://b2",
                bridgedb_url="https://example.org/Human/",
                cache_dir=tmp_path,
            )

        assert result.failed is False
        assert result.error is None
        assert result.hgnc_ids == {"11998"}


# ---------------------------------------------------------------------------
# Regression: all-fail and all-success paths are unchanged
# ---------------------------------------------------------------------------

class TestUnchangedPaths:
    """All-fail still writes _error; clean all-success has no _partial."""

    def test_all_chunks_fail_writes_error(self, tmp_path):
        """Test 5: every chunk fails -> {"_error": ...}, is_cached False."""
        bern2_dir = tmp_path / "bern2"
        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=requests.ConnectionError("all down"),
        ), patch("aopwiki_rdf.mapping.ner_el_mapper.time.sleep"):
            result = query_bern2(MIXED_TEXT, bern2_url="http://b2", cache_dir=bern2_dir)

        assert "_error" in result
        assert "_partial" not in result
        cached = _read_cache(tmp_path, MIXED_TEXT)
        assert "_error" in cached
        assert "_partial" not in cached
        assert is_cached(MIXED_TEXT, tmp_path) is False

    def test_all_chunks_succeed_no_partial(self, tmp_path):
        """Test 6: a clean chunked all-success writes annotations, no _partial,
        and is_cached True."""
        bern2_dir = tmp_path / "bern2"

        def side_effect(url, *a, **kw):
            sent = (kw.get("json") or {}).get("text", "")
            if sent == MIXED_TEXT:
                # Initial single-call attempt: error -> chunking fallback.
                raise requests.ConnectionError("force chunking")
            # Every chunk succeeds.
            return _bern2_response([TP53_ANN])

        with patch(
            "aopwiki_rdf.mapping.ner_el_mapper.requests.post",
            side_effect=side_effect,
        ), patch("aopwiki_rdf.mapping.ner_el_mapper.time.sleep"):
            result = query_bern2(MIXED_TEXT, bern2_url="http://b2", cache_dir=bern2_dir)

        assert "annotations" in result
        assert "_partial" not in result
        assert "_error" not in result
        cached = _read_cache(tmp_path, MIXED_TEXT)
        assert "_partial" not in cached
        assert "_error" not in cached
        assert is_cached(MIXED_TEXT, tmp_path) is True
