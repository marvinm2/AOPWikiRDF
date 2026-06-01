"""Offline tests for the BERN2 cache-coverage probe (NER-03 / COMPAT-01).

The coverage primitives are pure disk probes: they hash a (normalised)
description, look for ``{ner_cache_dir}/bern2/{_cache_key(text)}.json``, and
classify it as cached iff the file exists, parses, and carries no ``_error``
key. No network I/O. These tests build a tmp_path cache directory by hand and
assert the classification is correct, that ``_description_text`` matches the
prior inline normalisation byte-for-byte, and (COMPAT-01) that the probe makes
no network call and mutates no input dict.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers: write a cache entry the same way query_bern2 would
# ---------------------------------------------------------------------------

def _write_cache_entry(ner_cache_dir: Path, text: str, payload: dict) -> Path:
    """Write ``payload`` to the cache path the pipeline would look up.

    Mirrors ``find_hgnc_ids_via_ner_el``: BERN2 responses live under
    ``{ner_cache_dir}/bern2/{_cache_key(text)}.json``.
    """
    from aopwiki_rdf.mapping.ner_el_mapper import _cache_key

    bern2_dir = Path(ner_cache_dir) / "bern2"
    bern2_dir.mkdir(parents=True, exist_ok=True)
    path = bern2_dir / f"{_cache_key(text)}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _make_config(ner_cache_dir: Path):
    from aopwiki_rdf.config import PipelineConfig

    return PipelineConfig(ner_cache_dir=ner_cache_dir)


# ---------------------------------------------------------------------------
# _description_text -- byte-identical to the prior inline normalisation
# ---------------------------------------------------------------------------

class TestDescriptionText:
    """The factored helper must reproduce the old inline logic exactly."""

    def _old_inline(self, description):
        # Verbatim copy of the pre-refactor logic in map_ner_genes_in_kes
        # (lines ~414-417): list -> join stripped quotes, else strip quotes.
        if isinstance(description, list):
            return " ".join(str(d).strip('"') for d in description)
        return str(description).strip('"')

    def test_triple_quoted_string_matches_old(self):
        from aopwiki_rdf.mapping.ner_el_mapper import _description_text

        # The parser wraps descriptions as '"""..."""'.
        desc = '"""TP53 is a tumor suppressor gene."""'
        assert _description_text(desc) == self._old_inline(desc)
        # And the result is the unwrapped text.
        assert _description_text(desc) == "TP53 is a tumor suppressor gene."

    def test_list_of_descriptions_matches_old(self):
        from aopwiki_rdf.mapping.ner_el_mapper import _description_text

        desc = ['"""First block."""', '"""Second block."""']
        assert _description_text(desc) == self._old_inline(desc)
        assert _description_text(desc) == "First block. Second block."

    def test_plain_string_matches_old(self):
        from aopwiki_rdf.mapping.ner_el_mapper import _description_text

        desc = "no quotes here"
        assert _description_text(desc) == self._old_inline(desc)


# ---------------------------------------------------------------------------
# is_cached -- pure disk probe
# ---------------------------------------------------------------------------

class TestIsCached:
    """is_cached classifies present / absent / corrupt / _error entries."""

    def test_present_valid_entry_is_cached(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import is_cached

        text = "TP53 is a tumor suppressor."
        _write_cache_entry(tmp_path, text, {"annotations": []})
        assert is_cached(text, tmp_path) is True

    def test_absent_entry_is_not_cached(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import is_cached

        assert is_cached("never warmed text", tmp_path) is False

    def test_error_entry_is_not_cached(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import is_cached

        text = "failed once"
        _write_cache_entry(tmp_path, text, {"_error": "net down"})
        assert is_cached(text, tmp_path) is False

    def test_corrupt_entry_is_not_cached(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import is_cached, _cache_key

        text = "corrupt entry"
        bern2_dir = Path(tmp_path) / "bern2"
        bern2_dir.mkdir(parents=True, exist_ok=True)
        (bern2_dir / f"{_cache_key(text)}.json").write_text("not json {{{")
        assert is_cached(text, tmp_path) is False

    def test_probes_normalised_text(self, tmp_path):
        """is_cached must hash the SAME normalised text the pipeline uses, so
        a triple-quoted description warmed via its unwrapped text reads back
        as cached when probed with the unwrapped text."""
        from aopwiki_rdf.mapping.ner_el_mapper import is_cached, _description_text

        raw = '"""ACHE drives the effect."""'
        norm = _description_text(raw)
        _write_cache_entry(tmp_path, norm, {"annotations": []})
        assert is_cached(norm, tmp_path) is True


# ---------------------------------------------------------------------------
# report_cache_coverage -- counts, uncached IDs, logging
# ---------------------------------------------------------------------------

class TestReportCacheCoverage:
    """report_cache_coverage tallies cached/total and surfaces uncached IDs."""

    def test_mixed_cache_dir_classification(self, tmp_path, caplog):
        from aopwiki_rdf.mapping.ner_el_mapper import (
            report_cache_coverage,
            _description_text,
        )

        config = _make_config(tmp_path)
        kedict = {
            "1": {"dc:description": '"""TP53 cached."""'},
            "2": {"dc:description": '"""ACHE error."""'},
            "3": {"dc:description": '"""Never warmed."""'},
            "4": {"dc:description": "   "},          # whitespace only -> skip
            "5": {"rdfs:label": '"no description"'},  # no description -> skip
        }
        # KE 1 warmed OK, KE 2 has an _error entry, KE 3 absent.
        _write_cache_entry(tmp_path, _description_text(kedict["1"]["dc:description"]),
                           {"annotations": []})
        _write_cache_entry(tmp_path, _description_text(kedict["2"]["dc:description"]),
                           {"_error": "boom"})

        with caplog.at_level("INFO"):
            cov = report_cache_coverage(kedict, config=config)

        assert cov["total"] == 3          # KEs 1, 2, 3 (4 & 5 excluded)
        assert cov["cached"] == 1         # only KE 1
        assert cov["uncached_ids"] == ["2", "3"]  # sorted
        # One coverage line + one uncached-IDs line.
        assert any("BERN2 cache coverage" in r.message for r in caplog.records)
        assert any("1/3" in r.message for r in caplog.records)

    def test_accepts_multiple_dicts(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import (
            report_cache_coverage,
            _description_text,
        )

        config = _make_config(tmp_path)
        kedict = {"10": {"dc:description": '"""KE ten."""'}}
        kerdict = {"20": {"dc:description": '"""KER twenty."""'}}
        _write_cache_entry(tmp_path, _description_text(kedict["10"]["dc:description"]),
                           {"annotations": []})

        cov = report_cache_coverage(kedict, kerdict, config=config)
        assert cov["total"] == 2
        assert cov["cached"] == 1
        assert cov["uncached_ids"] == ["20"]

    def test_all_cached_reports_no_uncached(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import (
            report_cache_coverage,
            _description_text,
        )

        config = _make_config(tmp_path)
        kedict = {"1": {"dc:description": '"""Warm."""'}}
        _write_cache_entry(tmp_path, _description_text(kedict["1"]["dc:description"]),
                           {"annotations": []})
        cov = report_cache_coverage(kedict, config=config)
        assert cov["total"] == 1
        assert cov["cached"] == 1
        assert cov["uncached_ids"] == []

    def test_empty_input_is_safe(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import report_cache_coverage

        config = _make_config(tmp_path)
        cov = report_cache_coverage({}, config=config)
        assert cov["total"] == 0
        assert cov["cached"] == 0
        assert cov["uncached_ids"] == []

    def test_uncached_id_list_truncated_in_log(self, tmp_path, caplog):
        """When many IDs are uncached, the listing log line is truncated with
        a '+N more' suffix to bound log volume (T-06-02)."""
        from aopwiki_rdf.mapping.ner_el_mapper import report_cache_coverage

        config = _make_config(tmp_path)
        kedict = {
            str(i): {"dc:description": f'"""desc {i}."""'} for i in range(60)
        }
        with caplog.at_level("INFO"):
            cov = report_cache_coverage(kedict, config=config)
        assert cov["total"] == 60
        assert cov["cached"] == 0
        assert len(cov["uncached_ids"]) == 60
        assert any("more" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# COMPAT-01: coverage probe is observation-only
# ---------------------------------------------------------------------------

class TestCoverageIsInert:
    """The coverage path makes no network call and mutates no input dict."""

    def test_is_cached_makes_no_network_call(self, tmp_path):
        from aopwiki_rdf.mapping import ner_el_mapper

        with patch.object(
            ner_el_mapper.requests, "post",
            side_effect=AssertionError("network I/O is forbidden"),
        ) as m:
            ner_el_mapper.is_cached("anything", tmp_path)
        m.assert_not_called()

    def test_report_cache_coverage_makes_no_network_call(self, tmp_path):
        from aopwiki_rdf.mapping import ner_el_mapper

        config = _make_config(tmp_path)
        kedict = {"1": {"dc:description": '"""TP53."""'}}
        with patch.object(
            ner_el_mapper.requests, "post",
            side_effect=AssertionError("network I/O is forbidden"),
        ) as m:
            ner_el_mapper.report_cache_coverage(kedict, config=config)
        m.assert_not_called()

    def test_report_cache_coverage_does_not_mutate_input(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import report_cache_coverage
        import copy

        config = _make_config(tmp_path)
        kedict = {
            "1": {"dc:description": '"""TP53."""'},
            "2": {"dc:description": ['"""a."""', '"""b."""']},
            "3": {"rdfs:label": '"x"'},
        }
        kerdict = {"9": {"dc:description": '"""KER."""'}}
        before_ke = copy.deepcopy(kedict)
        before_ker = copy.deepcopy(kerdict)

        report_cache_coverage(kedict, kerdict, config=config)

        assert kedict == before_ke
        assert kerdict == before_ker
