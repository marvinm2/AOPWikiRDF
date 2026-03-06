"""Unit tests for the thin orchestrator (pipeline.py).

Verifies structural properties: module wiring, no exec(), line count,
API compatibility, and monolith preservation.
"""

import inspect

import pytest

from aopwiki_rdf import pipeline
from aopwiki_rdf.pipeline import main
from aopwiki_rdf.config import PipelineConfig


def test_main_accepts_config():
    """main() should accept a PipelineConfig parameter."""
    sig = inspect.signature(main)
    params = list(sig.parameters.keys())
    assert "config" in params


def test_main_accepts_none_default():
    """main() config parameter should default to None."""
    sig = inspect.signature(main)
    param = sig.parameters["config"]
    assert param.default is None


def test_orchestrator_imports_all_modules():
    """Orchestrator source must import from all extracted modules."""
    src = inspect.getsource(pipeline)
    assert "from aopwiki_rdf.parser.xml_parser import" in src
    assert "from aopwiki_rdf.mapping.gene_mapper import" in src
    assert "from aopwiki_rdf.mapping.chemical_mapper import" in src
    assert "from aopwiki_rdf.mapping.protein_ontology import" in src
    assert "from aopwiki_rdf.rdf.writer import" in src
    assert "from aopwiki_rdf.hgnc import" in src


def test_no_exec_in_orchestrator():
    """Regression guard: orchestrator must not use exec()."""
    src = inspect.getsource(pipeline)
    assert "exec(" not in src


def test_orchestrator_line_count():
    """Guard against re-monolithification: pipeline.py must be under 400 lines."""
    src = inspect.getsource(pipeline)
    line_count = len(src.splitlines())
    assert line_count < 400, f"pipeline.py has {line_count} lines (limit: 400)"


def test_monolith_preserved():
    """pipeline_monolith.py must exist and have >2000 lines."""
    from aopwiki_rdf import pipeline_monolith
    src = inspect.getsource(pipeline_monolith)
    line_count = len(src.splitlines())
    assert line_count > 2000, (
        f"pipeline_monolith.py has {line_count} lines (expected >2000)"
    )


def test_stages_defined():
    """Orchestrator must define named pipeline stages."""
    assert hasattr(pipeline, "STAGES")
    stage_names = [name for name, _fn in pipeline.STAGES]
    assert len(stage_names) >= 6, f"Expected at least 6 stages, got {len(stage_names)}"
    # Verify critical stages exist
    assert any("Parse" in n for n in stage_names)
    assert any("Gene" in n for n in stage_names)
    assert any("Chemical" in n for n in stage_names)
    assert any("VoID" in n for n in stage_names)


def test_context_dict_pattern():
    """Stages should use context dict pattern (function signatures)."""
    for name, fn in pipeline.STAGES:
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        assert "config" in params, f"Stage '{name}' missing 'config' parameter"
        assert "context" in params, f"Stage '{name}' missing 'context' parameter"
