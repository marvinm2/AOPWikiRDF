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
# load_prefix_block() / apply_prefixes() — namespace injection
# --------------------------------------------------------------------------- #

def test_load_prefix_block_parses_at_prefix_lines(tmp_path):
    (tmp_path / "a.ttl").write_text(
        "@prefix aopo: <http://aopkb.org/aop_ontology#> .\n"
        "@prefix : <https://aopwiki.rdf.bigcat-bioinformatics.org/> .\n"
        "@prefix hgnc: <https://identifiers.org/hgnc/>.\n"
        ":x a aopo:Thing .\n"
    )
    block = pf.load_prefix_block(tmp_path)
    assert "PREFIX aopo: <http://aopkb.org/aop_ontology#>" in block
    assert "PREFIX : <https://aopwiki.rdf.bigcat-bioinformatics.org/>" in block
    assert "PREFIX hgnc: <https://identifiers.org/hgnc/>" in block


def test_load_prefix_block_dedupes_by_name(tmp_path):
    (tmp_path / "a.ttl").write_text("@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n")
    (tmp_path / "b.ttl").write_text("@prefix foaf: <http://example.org/other#> .\n")
    block = pf.load_prefix_block(tmp_path)
    assert sum(1 for ln in block if ln.startswith("PREFIX foaf:")) == 1
    # first declaration wins
    assert "PREFIX foaf: <http://xmlns.com/foaf/0.1/>" in block


def test_apply_prefixes_prepends_missing():
    out = pf.apply_prefixes("SELECT * WHERE { ?s a aopo:X }",
                            ["PREFIX aopo: <http://aopkb.org/aop_ontology#>"])
    assert out.startswith("PREFIX aopo:")
    assert "SELECT * WHERE" in out


def test_apply_prefixes_skips_already_declared():
    q = "PREFIX aopo: <http://aopkb.org/aop_ontology#>\nSELECT * WHERE { ?s a aopo:X }"
    out = pf.apply_prefixes(q, ["PREFIX aopo: <http://example.org/other#>"])
    # the query's own declaration is kept; no duplicate prepended
    assert out.count("PREFIX aopo:") == 1
    assert "<http://example.org/other#>" not in out


def test_apply_prefixes_empty_block_is_noop():
    q = "SELECT * WHERE { ?s ?p ?o }"
    assert pf.apply_prefixes(q, []) == q


def test_substitute_graph_uri_replaces_token():
    q = "SELECT * WHERE { GRAPH __GRAPH_URI__ { ?s ?p ?o } }"
    out = pf.substitute_graph_uri(q, "http://aopwiki.org/")
    assert "__GRAPH_URI__" not in out
    assert "GRAPH <http://aopwiki.org/>" in out


def test_substitute_graph_uri_noop_without_token():
    q = "SELECT * WHERE { ?s ?p ?o }"
    assert pf.substitute_graph_uri(q, "http://aopwiki.org/") == q


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


def test_save_report_counts_flip_attributable_regressions(tmp_path):
    records = [
        # errored on both loads -> environmental, NOT flip-attributable
        {"source": "SNORQL", "name": "federated-q", "pre_count": 0, "post_count": 0,
         "status": "FAIL", "errored": True, "errored_pre": True,
         "flip_regression": False},
        # ran off-flip, errors on-flip -> flip-attributable regression
        {"source": "SNORQL", "name": "broke-by-flip", "pre_count": 5, "post_count": 0,
         "status": "FAIL", "errored": True, "errored_pre": False,
         "flip_regression": True},
    ]
    out = tmp_path / "preflight-report.md"
    pf.save_report(records, out)
    text = out.read_text()
    assert "**Flip-attributable regressions**: 1" in text
    assert "Flip verdict" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-x", "-q"]))
