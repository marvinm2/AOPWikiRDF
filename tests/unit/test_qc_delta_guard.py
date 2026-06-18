"""Offline, deterministic tests for the QC gene/triple delta guard.

These tests build tiny Turtle files in tmp_path directories and exercise
``scripts/qc_delta_guard.py`` without any network access. They prove that:

* identical inputs pass (no breach),
* a >threshold drop in gene associations trips the guard,
* an increase in triples passes (increases never breach),
* a missing new file is a hard breach,
* a within-threshold drop (under the default 5%) passes.

A final environment-dependent test compares the committed
``production-rdf-backup/`` files against themselves and asserts the guard
passes; it is skipped (not failed) when the backup is absent, matching the
repo's skipif convention for environment-dependent tests.
"""

import importlib.util
import os

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GUARD_PATH = os.path.join(PROJECT_ROOT, "scripts", "qc_delta_guard.py")
BACKUP_DIR = os.path.join(PROJECT_ROOT, "production-rdf-backup")


def _load_guard():
    """Import scripts/qc_delta_guard.py as a module (it lives outside a package)."""
    spec = importlib.util.spec_from_file_location("qc_delta_guard", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


TTL_HEADER = "@prefix edam: <http://edamontology.org/> .\n"


def _gene_ttl(n_genes):
    """Build a Turtle string with ``n_genes`` edam:data_1025 (gene) triples."""
    lines = [TTL_HEADER]
    for i in range(n_genes):
        lines.append(
            f"<http://example.org/ke/{i}> edam:data_1025 <http://example.org/gene/{i}> .\n"
        )
    return "".join(lines)


def _main_ttl(n_triples):
    """Build a Turtle string with ``n_triples`` arbitrary (non-gene) triples."""
    lines = [TTL_HEADER]
    for i in range(n_triples):
        lines.append(
            f"<http://example.org/s/{i}> <http://example.org/p> <http://example.org/o/{i}> .\n"
        )
    return "".join(lines)


def _write_pair(tmp_path, baseline_genes, new_genes, baseline_main=20, new_main=20,
                write_new_genes=True):
    """Create baseline/ and new/ dirs with -Genes.ttl and main TTL files.

    Returns (new_dir, baseline_dir) as strings.
    """
    baseline_dir = tmp_path / "baseline"
    new_dir = tmp_path / "new"
    baseline_dir.mkdir()
    new_dir.mkdir()

    (baseline_dir / "AOPWikiRDF-Genes.ttl").write_text(_gene_ttl(baseline_genes))
    (baseline_dir / "AOPWikiRDF.ttl").write_text(_main_ttl(baseline_main))

    (new_dir / "AOPWikiRDF.ttl").write_text(_main_ttl(new_main))
    if write_new_genes:
        (new_dir / "AOPWikiRDF-Genes.ttl").write_text(_gene_ttl(new_genes))

    return str(new_dir), str(baseline_dir)


def test_count_gene_associations(tmp_path):
    """count_gene_associations counts exactly the edam:data_1025 triples."""
    f = tmp_path / "g.ttl"
    f.write_text(_gene_ttl(7))
    g = guard.load_graph(str(f))
    assert guard.count_gene_associations(g) == 7


def test_count_triples(tmp_path):
    """count_triples returns the full triple count of the graph."""
    f = tmp_path / "m.ttl"
    f.write_text(_main_ttl(12))
    g = guard.load_graph(str(f))
    assert guard.count_triples(g) == 12


def test_identical_inputs_pass(tmp_path):
    """(a) new == baseline -> not breached, main() exits 0."""
    new_dir, baseline_dir = _write_pair(tmp_path, baseline_genes=100, new_genes=100)
    report = guard.run(new_dir, baseline_dir, drop_pct=0.05,
                       report_path=str(tmp_path / "r.json"))
    assert report["breached"] is False
    rc = guard.main([
        "--new-dir", new_dir,
        "--baseline-dir", baseline_dir,
        "--report-path", str(tmp_path / "r2.json"),
    ])
    assert rc == 0


def test_gene_drop_trips_guard(tmp_path):
    """(b) 50% fewer edam:data_1025 triples -> breached with a gene reason, exit 1."""
    new_dir, baseline_dir = _write_pair(tmp_path, baseline_genes=100, new_genes=50)
    report = guard.run(new_dir, baseline_dir, drop_pct=0.05,
                       report_path=str(tmp_path / "r.json"))
    assert report["breached"] is True
    reasons = " ".join(report["reasons"]).lower()
    assert "gene" in reasons
    rc = guard.main([
        "--new-dir", new_dir,
        "--baseline-dir", baseline_dir,
        "--report-path", str(tmp_path / "r2.json"),
    ])
    assert rc == 1


def test_increase_passes(tmp_path):
    """(c) more triples and more genes than baseline -> increase passes."""
    new_dir, baseline_dir = _write_pair(
        tmp_path, baseline_genes=100, new_genes=130,
        baseline_main=20, new_main=40,
    )
    report = guard.run(new_dir, baseline_dir, drop_pct=0.05,
                       report_path=str(tmp_path / "r.json"))
    assert report["breached"] is False


def test_missing_new_genes_file_is_breach(tmp_path):
    """(d) new -Genes.ttl missing -> hard breach, exit 1."""
    new_dir, baseline_dir = _write_pair(
        tmp_path, baseline_genes=100, new_genes=0, write_new_genes=False,
    )
    report = guard.run(new_dir, baseline_dir, drop_pct=0.05,
                       report_path=str(tmp_path / "r.json"))
    assert report["breached"] is True
    reasons = " ".join(report["reasons"]).lower()
    assert "missing" in reasons
    rc = guard.main([
        "--new-dir", new_dir,
        "--baseline-dir", baseline_dir,
        "--report-path", str(tmp_path / "r2.json"),
    ])
    assert rc == 1


def test_within_threshold_drop_passes(tmp_path):
    """(e) 3% drop with default 5% threshold -> within threshold, not breached."""
    # 100 -> 97 genes is a 3% drop; main 100 -> 97 also a 3% drop.
    new_dir, baseline_dir = _write_pair(
        tmp_path, baseline_genes=100, new_genes=97,
        baseline_main=100, new_main=97,
    )
    report = guard.run(new_dir, baseline_dir, drop_pct=0.05,
                       report_path=str(tmp_path / "r.json"))
    assert report["breached"] is False


def test_report_written(tmp_path):
    """run() writes a qc-delta-report.json with old-vs-new counts and deltas."""
    import json
    new_dir, baseline_dir = _write_pair(tmp_path, baseline_genes=100, new_genes=100)
    report_path = str(tmp_path / "qc-delta-report.json")
    guard.run(new_dir, baseline_dir, drop_pct=0.05, report_path=report_path)
    assert os.path.exists(report_path)
    with open(report_path) as fh:
        data = json.load(fh)
    assert "files" in data
    assert "breached" in data
    genes = next(f for f in data["files"] if f["file"] == "AOPWikiRDF-Genes.ttl")
    assert genes["baseline_genes"] == 100
    assert genes["new_genes"] == 100


requires_backup = pytest.mark.skipif(
    not os.path.exists(os.path.join(BACKUP_DIR, "AOPWikiRDF-Genes.ttl")),
    reason="production-rdf-backup/AOPWikiRDF-Genes.ttl not available",
)


@requires_backup
def test_real_backup_self_comparison_passes(tmp_path):
    """Real production-rdf-backup compared against itself must not breach.

    Locks the contract that an unchanged, real baseline (identical inputs)
    passes the guard with no false-positive abort on a steady week.
    """
    report = guard.run(BACKUP_DIR, BACKUP_DIR, drop_pct=0.05,
                       report_path=str(tmp_path / "real.json"))
    assert report["breached"] is False
    rc = guard.main([
        "--new-dir", BACKUP_DIR,
        "--baseline-dir", BACKUP_DIR,
        "--report-path", str(tmp_path / "real2.json"),
    ])
    assert rc == 0


# ---------------------------------------------------------------------------
# Phase 9 (XML-03) extensions: per-element relative-floor mode + --warn-only.
# Plan 04 implements the per-element guard mode and the --warn-only flag, so
# these tests now run as real (non-xfail) assertions.
# ---------------------------------------------------------------------------


def test_per_element_relative_floor(tmp_path):
    """Per-element guard uses a HEAD~1 relative floor, not an absolute one (D-10).

    A per-predicate drop beyond the relative floor breaches; the threshold is
    relative to the baseline count (1 - drop_pct), matching the gene/total
    relative-floor math the existing guard already uses. ``_main_ttl`` emits
    each arbitrary triple with predicate ``http://example.org/p``, so the main
    TTL's per-predicate count equals ``baseline_main`` / ``new_main`` — a real
    drop in that count exercises the relative floor (NOT an absolute one).
    """
    # Over-threshold: 100 -> 50 for the tracked predicate (50% drop) breaches.
    new_dir, baseline_dir = _write_pair(
        tmp_path, baseline_genes=100, new_genes=100,
        baseline_main=100, new_main=50,
    )
    # Plan 04 sources the element->predicate map from
    # coverage-ratchet-baseline.json and applies the same relative-floor check
    # per element.
    report = guard.run(
        new_dir, baseline_dir, drop_pct=0.05,
        report_path=str(tmp_path / "r.json"),
        per_element=True,
        element_predicates={
            "key-event-relationship": "http://example.org/p",
        },
    )
    assert "per_element" in report
    entry = report["per_element"]["key-event-relationship"]
    assert entry["baseline_count"] == 100
    assert entry["new_count"] == 50
    assert entry["breached"] is True
    assert report["breached"] is True

    # Within-threshold: a 3% drop (100 -> 97) stays under the 5% relative floor
    # and must NOT breach — proving the floor is relative, not an absolute count.
    within_root = tmp_path / "within"
    within_root.mkdir()
    within_new, within_base = _write_pair(
        within_root, baseline_genes=100, new_genes=100,
        baseline_main=100, new_main=97,
    )
    within_report = guard.run(
        within_new, within_base, drop_pct=0.05,
        report_path=str(tmp_path / "within" / "r.json"),
        per_element=True,
        element_predicates={"key-event-relationship": "http://example.org/p"},
    )
    assert within_report["per_element"]["key-event-relationship"]["breached"] is False


def test_warn_only_exits_zero(tmp_path, capsys):
    """``--warn-only`` exits 0 and emits ``::warning::`` even on a breach (D-08).

    Weekly posture: a transient upstream hiccup must not stall the data
    release, so the publish-gate runs the guard in warn-only mode.
    """
    new_dir, baseline_dir = _write_pair(tmp_path, baseline_genes=100, new_genes=50)
    rc = guard.main([
        "--new-dir", new_dir,
        "--baseline-dir", baseline_dir,
        "--report-path", str(tmp_path / "r.json"),
        "--warn-only",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "::warning::" in out
