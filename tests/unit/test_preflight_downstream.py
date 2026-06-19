#!/usr/bin/env python3
"""
Nyquist unit tests for scripts/preflight_downstream.py.

Covers the PURE, network-free helpers (Task 1 of plan 12-02):
  - .rq corpus loader (header stripping + {{param}} Mustache substitution)
  - methodology_notes.json corpus loader
  - classify() implementing the D-05 pass/fail bar
  - save_report() dict-to-Markdown emission

No SPARQL/Docker is touched here; loaders read fixtures read-only.
"""

import json
import sys
from pathlib import Path

import pytest

# Make scripts/ importable regardless of CWD.
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import preflight_downstream as pf  # noqa: E402


# --------------------------------------------------------------------------- #
# .rq corpus loader
# --------------------------------------------------------------------------- #

def test_rq_loader_discovers_files_and_strips_headers(tmp_path):
    cat = tmp_path / "B. AOPs"
    cat.mkdir()
    (cat / "all-aops.rq").write_text(
        "# title: All AOPs\n"
        "# description: lists them\n"
        "# category: AOPs\n"
        "\n"
        "SELECT ?aop WHERE { ?aop a aopo:AdverseOutcomePathway . }\n"
    )
    (cat / "one-ke.rq").write_text(
        "# title: One KE\n"
        "SELECT ?ke WHERE { ?ke a aopo:KeyEvent . }\n"
    )

    records = pf.load_rq_corpus(tmp_path)

    assert len(records) == 2
    for rec in records:
        assert set(rec) >= {"source", "name", "query"}
        # No comment/header lines survive in the query body.
        for line in rec["query"].splitlines():
            assert not line.lstrip().startswith("#")
        assert "SELECT" in rec["query"]


def test_rq_loader_substitutes_mustache_param_default(tmp_path):
    cat = tmp_path / "D. KERs"
    cat.mkdir()
    (cat / "kers-for-aop.rq").write_text(
        "# title: List KERs in an AOP\n"
        "# param: aop_id|autocomplete:aop|12|AOP\n"
        "\n"
        "SELECT ?KER WHERE { aop:{{aop_id}} aopo:has_key_event_relationship ?KER . }\n"
    )

    records = pf.load_rq_corpus(tmp_path)

    assert len(records) == 1
    body = records[0]["query"]
    assert "{{aop_id}}" not in body
    assert "aop:12" in body


# --------------------------------------------------------------------------- #
# methodology_notes.json corpus loader
# --------------------------------------------------------------------------- #

def test_json_loader_pulls_sparql_per_entry(tmp_path):
    notes = {
        "latest_entity_counts": {
            "title": "Entity counts",
            "sparql": "SELECT (COUNT(?s) AS ?n) WHERE { ?s ?p ?o }",
        },
        "ke_components": {
            "title": "KE components",
            "sparql": "SELECT ?ke WHERE { ?ke a aopo:KeyEvent }",
        },
    }
    p = tmp_path / "methodology_notes.json"
    p.write_text(json.dumps(notes))

    records = pf.load_json_corpus(p)

    assert len(records) == 2
    names = {r["name"] for r in records}
    assert names == {"latest_entity_counts", "ke_components"}
    for rec in records:
        assert set(rec) >= {"source", "name", "query"}
        assert "SELECT" in rec["query"]


def test_json_loader_expands_multi_query_entries(tmp_path):
    # Some methodology_notes entries carry a `queries` list of {caption, query}
    # sub-queries instead of a single `sparql` key; all sub-queries must be covered.
    notes = {
        "ke_components": {
            "title": "KE components",
            "queries": [
                {"caption": "objects", "query": "SELECT ?o WHERE { ?ke ?p ?o }"},
                {"caption": "processes", "query": "SELECT ?pr WHERE { ?ke ?p ?pr }"},
            ],
        },
        "single": {
            "title": "single",
            "sparql": "SELECT ?s WHERE { ?s ?p ?o }",
        },
    }
    p = tmp_path / "methodology_notes.json"
    p.write_text(json.dumps(notes))

    records = pf.load_json_corpus(p)

    names = {r["name"] for r in records}
    assert "ke_components::objects" in names
    assert "ke_components::processes" in names
    assert "single" in names
    assert len(records) == 3


def test_json_loader_skips_entries_without_sparql(tmp_path):
    notes = {
        "has_q": {"title": "ok", "sparql": "SELECT ?s WHERE { ?s ?p ?o }"},
        "no_q": {"title": "prose only", "description": "no query here"},
    }
    p = tmp_path / "methodology_notes.json"
    p.write_text(json.dumps(notes))

    records = pf.load_json_corpus(p)

    assert {r["name"] for r in records} == {"has_q"}


# --------------------------------------------------------------------------- #
# classify() — the D-05 bar
# --------------------------------------------------------------------------- #

def test_classify_row_regression_is_fail():
    assert pf.classify(pre_count=1, post_count=0, errored=False) == "FAIL"


def test_classify_zero_to_zero_is_pass():
    assert pf.classify(pre_count=0, post_count=0, errored=False) == "PASS"


def test_classify_rising_counts_is_pass():
    assert pf.classify(pre_count=3, post_count=9, errored=False) == "PASS"


def test_classify_equal_nonzero_is_pass():
    assert pf.classify(pre_count=5, post_count=5, errored=False) == "PASS"


def test_classify_errored_is_fail_even_at_zero_zero():
    assert pf.classify(pre_count=0, post_count=0, errored=True) == "FAIL"


def test_classify_zero_to_nonzero_is_pass():
    # New rows appearing where there were none is additive, not a regression.
    assert pf.classify(pre_count=0, post_count=4, errored=False) == "PASS"


# --------------------------------------------------------------------------- #
# save_report()
# --------------------------------------------------------------------------- #

def test_save_report_writes_markdown_table(tmp_path):
    records = [
        {"source": "SNORQL", "name": "all-aops", "pre_count": 3,
         "post_count": 9, "status": "PASS", "errored": False},
        {"source": "methodology_notes", "name": "ke_components", "pre_count": 1,
         "post_count": 0, "status": "FAIL", "errored": False},
    ]
    out = tmp_path / "preflight-report.md"

    pf.save_report(records, out)

    text = out.read_text()
    assert "| Status" in text or "Status |" in text  # a Markdown table header
    assert "PASS" in text and "FAIL" in text
    assert "all-aops" in text and "ke_components" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-x", "-q"]))
