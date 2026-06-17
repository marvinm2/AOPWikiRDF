"""Unit tests for the XML→RDF coverage audit (XML-01).

These tests pin the behavior of the not-yet-implemented
``scripts/coverage_audit.py`` (Plan 02). They are laid down in Wave 0 with
real assertions but ``xfail``-marked, so the suite is green-on-red: each test
will start *passing* (and the xfail flips to xpass) once Plan 02 implements the
audit. They run against the small ``sample_aopwiki_coverage.xml`` fixture, never
the 48 MB production snapshot.

Behavior map (locked from 09-VALIDATION.md § Per-Task Verification Map):

* ``test_audit_emits_json``        — XML-01 headline: per-element coverage bool,
                                     occurrence counts, deltas, written as JSON.
* ``test_attribute_axis``          — enumeration is namespace-qualified AND walks
                                     attributes (D-03), not just elements.
* ``test_covered_set``             — covered set derived from the parser source,
                                     including ``.get('...')`` attribute reads, so
                                     ``id`` / ``key-event-id`` / ``taxonomy-id``
                                     are NOT falsely reported as gaps (Pitfall 7).
* ``test_no_snapshots_dir_skips``  — historical walk skips gracefully when the
                                     snapshots dir is absent (D-04 / Pitfall 6).
* ``test_allowlist``               — allowlisted elements (D-09) are excluded from
                                     the gap set.
"""

import importlib.util
import json
import os

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUDIT_PATH = os.path.join(PROJECT_ROOT, "scripts", "coverage_audit.py")
FIXTURE = os.path.join(PROJECT_ROOT, "tests", "fixtures", "sample_aopwiki_coverage.xml")
ALLOWLIST = os.path.join(PROJECT_ROOT, "data", "schema", "coverage-allowlist.json")


def _load_audit():
    """Import scripts/coverage_audit.py as a module (it lives outside a package).

    Mirrors the spec_from_file_location idiom in test_qc_delta_guard.py.
    """
    spec = importlib.util.spec_from_file_location("coverage_audit", AUDIT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_audit_emits_json(tmp_path):
    """Audit writes JSON with per-element coverage bool + occurrence counts."""
    audit = _load_audit()
    report_path = tmp_path / "coverage-report.json"
    audit.run(xml_path=FIXTURE, allowlist_path=ALLOWLIST,
              report_path=str(report_path), snapshots_dir=None)
    assert report_path.exists()
    data = json.loads(report_path.read_text())
    # Per-element records carry a coverage flag and an occurrence count.
    elements = data["elements"]
    rec = elements["key-event-relationship"]
    assert "covered" in rec
    assert rec["occurrences"] >= 1


def test_attribute_axis(tmp_path):
    """Enumeration is namespace-qualified and walks attributes too (D-03)."""
    audit = _load_audit()
    report_path = tmp_path / "coverage-report.json"
    data = audit.run(xml_path=FIXTURE, allowlist_path=ALLOWLIST,
                     report_path=str(report_path), snapshots_dir=None)
    # The (element, attribute) axis must be enumerated, e.g. key-event/key-event-id.
    attrs = data["attributes"]
    assert any("key-event-id" in str(k) for k in attrs), attrs


def test_covered_set(tmp_path):
    """Covered set derives from parser source incl. .get() attribute reads.

    The attribute IDs the parser reads via ``.get('...')`` (e.g. id,
    key-event-id, taxonomy-id) must NOT appear as gaps (Pitfall 7).
    """
    audit = _load_audit()
    report_path = tmp_path / "coverage-report.json"
    data = audit.run(xml_path=FIXTURE, allowlist_path=ALLOWLIST,
                     report_path=str(report_path), snapshots_dir=None)
    gaps = set(data["gaps"])
    for attr_id in ("id", "key-event-id", "taxonomy-id", "stressor-id"):
        assert attr_id not in gaps, f"{attr_id} falsely reported as a gap"


@pytest.mark.xfail(
    reason="graceful historical-walk skip wired in Plan 02 Task 2",
    strict=False,
)
def test_no_snapshots_dir_skips(tmp_path):
    """Historical snapshot walk skips gracefully when the dir is absent (D-04)."""
    audit = _load_audit()
    report_path = tmp_path / "coverage-report.json"
    missing = tmp_path / "does-not-exist"
    # Must not raise; report still produced from the single latest snapshot.
    data = audit.run(xml_path=FIXTURE, allowlist_path=ALLOWLIST,
                     report_path=str(report_path), snapshots_dir=str(missing))
    assert report_path.exists()
    assert "elements" in data


def test_allowlist(tmp_path):
    """Allowlisted elements (D-09) are excluded from the gap set."""
    audit = _load_audit()
    report_path = tmp_path / "coverage-report.json"
    data = audit.run(xml_path=FIXTURE, allowlist_path=ALLOWLIST,
                     report_path=str(report_path), snapshots_dir=None)
    gaps = set(data["gaps"])
    # 'references' is present in the fixture but allowlisted -> not a gap.
    assert "references" not in gaps
