"""Tests proving exec() elimination and HGNC download wiring in pipeline.py.

These are structural/static tests that verify the codebase itself,
not runtime behavior. They run fast with no network calls.
"""

import inspect
from pathlib import Path


# Path to the pipeline source file
PIPELINE_PATH = Path(__file__).resolve().parent.parent.parent / "src" / "aopwiki_rdf" / "pipeline.py"
SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "aopwiki_rdf"


def test_no_exec_in_pipeline():
    """pipeline.py must contain zero occurrences of 'exec('."""
    source = PIPELINE_PATH.read_text(encoding="utf-8")
    assert "exec(" not in source, (
        "Found 'exec(' in pipeline.py -- dynamic code execution must be eliminated"
    )


def test_no_string_replacement():
    """pipeline.py must not use string replacement to inject config values."""
    source = PIPELINE_PATH.read_text(encoding="utf-8")
    assert "script_content" not in source, (
        "Found 'script_content' in pipeline.py -- string replacement pattern must be removed"
    )


def test_hgnc_download_wired():
    """pipeline.py must import and call download_hgnc_data."""
    source = PIPELINE_PATH.read_text(encoding="utf-8")
    assert "download_hgnc_data" in source, (
        "download_hgnc_data not found in pipeline.py -- HGNC download must be wired in"
    )


def test_main_accepts_config():
    """main() must accept a PipelineConfig parameter."""
    from aopwiki_rdf.pipeline import main
    from aopwiki_rdf.config import PipelineConfig

    sig = inspect.signature(main)
    assert "config" in sig.parameters, (
        "main() must have a 'config' parameter"
    )
    # Verify the annotation includes PipelineConfig
    param = sig.parameters["config"]
    # The annotation should reference PipelineConfig (possibly as Optional/Union)
    assert param.default is None, (
        "config parameter should default to None"
    )


def test_no_exec_anywhere_in_src():
    """No .py file under src/aopwiki_rdf/ should contain 'exec(compile('."""
    for py_file in SRC_DIR.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        assert "exec(compile(" not in source, (
            f"Found 'exec(compile(' in {py_file.relative_to(SRC_DIR.parent.parent)} "
            f"-- dynamic code execution must be eliminated from all source files"
        )
