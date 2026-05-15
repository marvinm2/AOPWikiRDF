"""Integration tests for the ARR-AOP filter stage.

Exercises `_stage_filter_arr_aops` against a real parse of the sample fixture
(which contains one BY-SA AOP and one ARR AOP) to confirm:

- default `filter_arr_aops=False` keeps all AOPs in aopdict;
- `filter_arr_aops=True` drops ARR-licensed AOPs only.
"""

from pathlib import Path


def _build_context_from_fixture(fixture_path):
    """Parse the fixture and return a pipeline-context-shaped dict."""
    from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml
    entities = parse_aopwiki_xml(str(fixture_path))
    return {"entities": entities}


def test_filter_arr_aops_default_off(sample_xml_path):
    """With the default config (filter_arr_aops=False), both AOPs remain."""
    from aopwiki_rdf.config import PipelineConfig
    from aopwiki_rdf.pipeline import _stage_filter_arr_aops

    cfg = PipelineConfig()
    assert cfg.filter_arr_aops is False  # explicit default check

    context = _build_context_from_fixture(sample_xml_path)
    before = set(context["entities"].aopdict.keys())
    _stage_filter_arr_aops(cfg, context)
    after = set(context["entities"].aopdict.keys())

    assert before == after
    assert '1' in after  # BY-SA
    assert '2' in after  # ARR


def test_filter_arr_aops_on_drops_arr(sample_xml_path):
    """With filter_arr_aops=True, only the ARR AOP is removed."""
    from aopwiki_rdf.config import PipelineConfig
    from aopwiki_rdf.pipeline import _stage_filter_arr_aops

    cfg = PipelineConfig(filter_arr_aops=True)
    context = _build_context_from_fixture(sample_xml_path)
    _stage_filter_arr_aops(cfg, context)

    remaining = set(context["entities"].aopdict.keys())
    assert '1' in remaining          # BY-SA kept
    assert '2' not in remaining      # ARR dropped


def test_filter_arr_aops_keeps_ke_ker(sample_xml_path):
    """Filter is AOP-only: KEs, KERs, and Stressors are untouched."""
    from aopwiki_rdf.config import PipelineConfig
    from aopwiki_rdf.pipeline import _stage_filter_arr_aops

    cfg = PipelineConfig(filter_arr_aops=True)
    context = _build_context_from_fixture(sample_xml_path)
    kes_before = set(context["entities"].kedict.keys())
    kers_before = set(context["entities"].kerdict.keys())
    stressors_before = set(context["entities"].stressordict.keys())

    _stage_filter_arr_aops(cfg, context)

    assert kes_before == set(context["entities"].kedict.keys())
    assert kers_before == set(context["entities"].kerdict.keys())
    assert stressors_before == set(context["entities"].stressordict.keys())
