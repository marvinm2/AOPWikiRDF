"""Integration tests for the coverage ratchet (XML-02 / XML-03).

* ``test_fixed_gaps_emit`` — XML-02: each fixed gap element now emits its
  triple(s) in writer output. Depends on the Plan 03 parser/writer gap-fix;
  xfail until then.
* ``test_additive`` — XML-02: gap fixes are additive, the total triple count
  does not drop. Depends on Plan 03; xfail until then.
* ``test_ratchet_fails_on_drop`` — XML-03 (the critical Nyquist NEGATIVE
  sample): when a covered element drops out of the output below the relative
  floor, the ratchet MUST breach (exit 1). This one is real and passing in
  Wave 0 — a ratchet that cannot be shown to fail is not validated. It exercises
  the existing relative-floor breach mechanism in scripts/qc_delta_guard.py.
"""

import importlib.util
import os

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GUARD_PATH = os.path.join(PROJECT_ROOT, "scripts", "qc_delta_guard.py")

TTL_HEADER = "@prefix edam: <http://edamontology.org/> .\n"


def _load_guard():
    spec = importlib.util.spec_from_file_location("qc_delta_guard", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gene_ttl(n):
    lines = [TTL_HEADER]
    for i in range(n):
        lines.append(
            f"<http://example.org/ke/{i}> edam:data_1025 <http://example.org/gene/{i}> .\n"
        )
    return "".join(lines)


def _main_ttl(n):
    lines = [TTL_HEADER]
    for i in range(n):
        lines.append(
            f"<http://example.org/s/{i}> <http://example.org/p> <http://example.org/o/{i}> .\n"
        )
    return "".join(lines)


def test_ratchet_fails_on_drop(tmp_path):
    """NEGATIVE sample: a covered element dropping below the relative floor breaches.

    Builds a baseline graph and a "new" graph that drops a covered (gene)
    element well below the 5% relative floor, then asserts the guard reports a
    breach and ``main`` exits 1. This proves the ratchet can fail — without a
    demonstrable failure the ratchet is not validated.
    """
    guard = _load_guard()
    baseline_dir = tmp_path / "baseline"
    new_dir = tmp_path / "new"
    baseline_dir.mkdir()
    new_dir.mkdir()

    # Baseline covers 100 elements; the new output drops to 50 (a 50% drop,
    # far below the 5% relative floor) — the covered element fell out.
    (baseline_dir / "AOPWikiRDF-Genes.ttl").write_text(_gene_ttl(100))
    (baseline_dir / "AOPWikiRDF.ttl").write_text(_main_ttl(20))
    (new_dir / "AOPWikiRDF-Genes.ttl").write_text(_gene_ttl(50))
    (new_dir / "AOPWikiRDF.ttl").write_text(_main_ttl(20))

    report = guard.run(str(new_dir), str(baseline_dir), drop_pct=0.05,
                       report_path=str(tmp_path / "r.json"))
    assert report["breached"] is True

    rc = guard.main([
        "--new-dir", str(new_dir),
        "--baseline-dir", str(baseline_dir),
        "--report-path", str(tmp_path / "r2.json"),
    ])
    assert rc == 1


@pytest.mark.xfail(
    reason="gap-fix parser/writer not yet implemented — Plan 03",
    strict=False,
)
def test_fixed_gaps_emit(tmp_path):
    """Each fixed gap element now emits its triple(s) in writer output (XML-02)."""
    # Plan 03 wires the parser to read the gap elements
    # (evidence-collection-strategy, time-scale) and the writer to emit their
    # predicates. Until then this assertion fails -> xfail.
    from aopwiki_rdf.parser import xml_parser  # noqa: F401
    from aopwiki_rdf.rdf import writer  # noqa: F401

    fixture = os.path.join(PROJECT_ROOT, "tests", "fixtures",
                           "sample_aopwiki_coverage.xml")
    # The gap-fix predicates must appear in the emitted Turtle for the
    # fixture's evidence-collection-strategy / time-scale gap elements.
    assert hasattr(writer, "write_aop_rdf")
    # Placeholder assertion that Plan 03 will satisfy by emitting the new triple.
    assert os.path.exists(fixture)
    raise AssertionError("gap-fix triple emission not yet implemented (Plan 03)")


@pytest.mark.xfail(
    reason="gap-fix additive check depends on Plan 03 output — Plan 03",
    strict=False,
)
def test_additive(tmp_path):
    """Gap fixes are additive — total triple count does not drop (XML-02)."""
    # Plan 03's gap-fixes only ADD triples; the total must be >= the
    # pre-fix baseline. Until the gap-fix lands there is nothing to compare.
    raise AssertionError("gap-fix additive baseline not yet available (Plan 03)")
