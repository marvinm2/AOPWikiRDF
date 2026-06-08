"""Offline tests for the 3-field KER NER corpus + cache-coverage probe (D-09a/b).

KER NER must reach method parity with the regex mapper, which scans three KER
text fields: ``dc:description`` (the relationship description), ``nci:C80263``
(biological-plausibility) and ``edam:data_2042`` (empirical-support). A single
``_ker_ner_texts`` helper is the source of truth for "what KER text gets
annotated", shared by ``map_ner_genes_in_kers`` AND ``report_cache_coverage``
so cache keys always agree.

These tests are pure disk probes (no network I/O): they build a tmp_path cache
directory by hand and assert
  * ``_ker_ner_texts`` yields one normalised block per non-empty field and
    skips empty/missing ones (using the existing ``_description_text``
    normaliser, byte-for-byte);
  * ``report_cache_coverage`` over a kerdict counts EACH of the three field
    texts as its own cache entry (the total reflects all three, not just
    ``dc:description``) — the warning-sign guard against a narrow probe;
  * a KER is reported "cached" ONLY when ALL of its texts are cached (warm 2
    of 3 -> still uncached).
"""

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers (mirror tests/unit/test_ner_cache_coverage.py)
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


# A KER carrying all three NER text fields, each parser-wrapped in '"""..."""'.
def _three_field_ker() -> dict:
    return {
        "dc:description": '"""The KER links TP53 to apoptosis."""',
        "nci:C80263": '"""Biological plausibility involves ACHE signalling."""',
        "edam:data_2042": '"""Empirical support from EGFR studies."""',
    }


# ---------------------------------------------------------------------------
# _ker_ner_texts -- single source of truth for "what KER text gets annotated"
# ---------------------------------------------------------------------------

class TestKerNerTexts:
    """_ker_ner_texts yields one normalised, non-blank block per present field."""

    def test_three_present_fields_yield_three_texts(self):
        from aopwiki_rdf.mapping.ner_el_mapper import _ker_ner_texts, _description_text

        props = _three_field_ker()
        texts = _ker_ner_texts(props)
        assert len(texts) == 3
        # Each is the unwrapped, normalised form of its source field.
        assert _description_text(props["dc:description"]) in texts
        assert _description_text(props["nci:C80263"]) in texts
        assert _description_text(props["edam:data_2042"]) in texts

    def test_missing_and_empty_fields_skipped(self):
        from aopwiki_rdf.mapping.ner_el_mapper import _ker_ner_texts

        props = {
            "dc:description": '"""Only this one is present."""',
            "nci:C80263": "",            # empty -> skip
            "edam:data_2042": '"""   """',  # whitespace-only after unwrap -> skip
        }
        texts = _ker_ner_texts(props)
        assert texts == ["Only this one is present."]

    def test_no_ner_fields_yields_empty_list(self):
        from aopwiki_rdf.mapping.ner_el_mapper import _ker_ner_texts

        assert _ker_ner_texts({"rdfs:label": '"no ner text"'}) == []


# ---------------------------------------------------------------------------
# report_cache_coverage over a kerdict -- counts ALL THREE fields
# ---------------------------------------------------------------------------

class TestKerCoverageCountsAllThreeFields:
    """The probe must count each KER field text as its own cache entry."""

    def test_probe_total_reflects_all_three_fields(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import (
            report_cache_coverage,
            _ker_ner_texts,
        )

        config = _make_config(tmp_path)
        kerdict = {"50": _three_field_ker()}
        # Warm every one of the KER's texts.
        for text in _ker_ner_texts(kerdict["50"]):
            _write_cache_entry(tmp_path, text, {"annotations": []})

        cov = report_cache_coverage(kerdict, config=config)
        # Warning-sign guard: a narrow (dc:description-only) probe would report
        # total == 1. Counting all three fields makes total == 3.
        assert cov["total"] == 3
        assert cov["cached"] == 3
        assert cov["uncached_ids"] == []

    def test_ker_cached_requires_all_fields(self, tmp_path):
        from aopwiki_rdf.mapping.ner_el_mapper import (
            report_cache_coverage,
            _ker_ner_texts,
        )

        config = _make_config(tmp_path)
        kerdict = {"50": _three_field_ker()}
        texts = _ker_ner_texts(kerdict["50"])
        # Warm only 2 of the 3 KER texts -> the KER is NOT fully cached.
        for text in texts[:2]:
            _write_cache_entry(tmp_path, text, {"annotations": []})

        cov = report_cache_coverage(kerdict, config=config)
        assert cov["total"] == 3
        assert cov["cached"] == 2
        # The KER is reported uncached because one of its fields is missing.
        assert "50" in cov["uncached_ids"]

    def test_ke_dicts_still_count_single_description(self, tmp_path):
        """KE dicts (no nci:C80263/edam:data_2042) keep single-field counting."""
        from aopwiki_rdf.mapping.ner_el_mapper import (
            report_cache_coverage,
            _description_text,
        )

        config = _make_config(tmp_path)
        kedict = {"100": {"dc:description": '"""KE only has a description."""'}}
        _write_cache_entry(
            tmp_path, _description_text(kedict["100"]["dc:description"]),
            {"annotations": []},
        )
        cov = report_cache_coverage(kedict, config=config)
        assert cov["total"] == 1
        assert cov["cached"] == 1
        assert cov["uncached_ids"] == []
