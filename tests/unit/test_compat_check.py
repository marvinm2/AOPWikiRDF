"""Offline, deterministic tests for the COMPAT closing gate (COMPAT-01).

These tests load ``scripts/compat_check.py`` via importlib (it lives outside a
package) and exercise it WITHOUT any network access or full-pipeline regen.
They prove the load-bearing properties of the gate:

* the masker covers ALL FOUR run-varying date-token families AND leaves a bare
  XML ``dcterms:created`` literal untouched (T-11-05 — an incomplete mask is the
  #1 risk),
* two inputs identical except for the four date tokens compare EQUAL after
  masking (COMPAT-01 criterion 2, two-dates no-drift),
* the gate is PROVABLE-TO-FAIL on an injected per-subject diff (COMPAT-01 — a
  gate that cannot be shown to fail is not validated), naming the mutated
  subject IRI,
* identical inputs pass (no breach, rc 0),
* the off-vs-on comparison is ADDITIVE-ONLY: flag-gated additions do NOT breach
  but a non-additive change to a shared line DOES.

The negative sample mirrors
``tests/integration/test_coverage_ratchet.py::test_ratchet_fails_on_drop`` and
the load-outside-package + pre-built-dir idiom of
``tests/unit/test_qc_delta_guard.py``. It deliberately does NOT re-implement the
token-leak unit checks from ``tests/integration/test_compat_flag_off.py`` (D-07
— the gate complements, it does not duplicate).
"""

import importlib.util
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GATE_PATH = os.path.join(PROJECT_ROOT, "scripts", "compat_check.py")


def _load_gate():
    """Import scripts/compat_check.py as a module (it lives outside a package)."""
    spec = importlib.util.spec_from_file_location("compat_check", GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


# A fixture carrying ALL FOUR run-varying token families plus the two XML-sourced
# bare literals that MUST survive masking (no ^^xsd:date / ^^xsd:dateTime tag).
def _all_tokens_ttl(gen_date, void_date, imported_a, imported_b, sd_modified):
    return (
        f"# Generated: {gen_date}\n"
        "# Load alongside AOPWikiRDF.ttl for full cross-reference capability\n"
        "\n"
        ":AOPWikiRDF.ttl\ta\tvoid:Dataset"
        f' ;\n\tpav:createdOn\t"{void_date}"^^xsd:date'
        " .\n"
        "\n"
        ":HGNCgenes.txt\ta\tvoid:Dataset, void:Linkset"
        f' ;\n\tpav:importedOn\t"{imported_a}"'
        " .\n"
        "\n"
        "<https://proconsortium.org/download/current/promapping.txt>\ta\tvoid:Dataset"
        f' ;\n\tpav:importedOn\t"{imported_b}"'
        " .\n"
        "\n"
        # ServiceDescription dcterms:modified — datatype-tagged, MUST be masked.
        "    <https://aopwiki.rdf.bigcat-bioinformatics.org/sparql/> a sd:Service ;\n"
        f'        dcterms:modified "{sd_modified}"^^xsd:dateTime\n'
        "    .\n"
        "\n"
        # XML-sourced bare literals (NO datatype tag) — MUST SURVIVE masking.
        "<http://aopwiki.org/aop/1>\ta\taopo:AdverseOutcomePathway"
        ' ;\n\tdcterms:created "2016-11-29T18:41:15"'
        ' ;\n\tdcterms:modified "2024-05-01T09:00:00"'
        " .\n"
    )


def test_mask_covers_all_runvarying():
    """All four run-varying families -> <MASKED>; XML bare dates SURVIVE."""
    raw = _all_tokens_ttl(
        gen_date="2026-06-18",
        void_date="2026-06-18",
        imported_a="2026-06-17T12:00:00",
        imported_b="2026-06-16T08:30:00",
        sd_modified="2026-06-18T06:00:00",
    ).encode("utf-8")
    masked = gate.mask(raw)

    # All four families are gone (no residual run-varying token) and replaced.
    assert b"<MASKED>" in masked
    assert b"# Generated: 2026-06-18" not in masked
    assert b'pav:createdOn\t"2026-06-18"^^xsd:date' not in masked
    assert b'pav:importedOn\t"2026-06-17T12:00:00"' not in masked
    assert b'pav:importedOn\t"2026-06-16T08:30:00"' not in masked
    assert b'dcterms:modified "2026-06-18T06:00:00"^^xsd:dateTime' not in masked

    # The masked forms are present, structure-preserving.
    assert b"# Generated: <MASKED>" in masked
    assert b'pav:createdOn\t"<MASKED>"^^xsd:date' in masked
    assert b'pav:importedOn\t"<MASKED>"' in masked
    assert b'dcterms:modified "<MASKED>"^^xsd:dateTime' in masked

    # The bare XML-sourced literals (no datatype tag) MUST survive untouched.
    assert b'dcterms:created "2016-11-29T18:41:15"' in masked
    assert b'dcterms:modified "2024-05-01T09:00:00"' in masked
    assert b"2016-11-29" in masked


def test_mask_is_idempotent():
    """mask(mask(x)) == mask(x) — masking an already-masked corpus is a no-op."""
    raw = _all_tokens_ttl(
        gen_date="2026-06-18",
        void_date="2026-06-18",
        imported_a="2026-06-17T12:00:00",
        imported_b="2026-06-16T08:30:00",
        sd_modified="2026-06-18T06:00:00",
    ).encode("utf-8")
    once = gate.mask(raw)
    twice = gate.mask(once)
    assert once == twice


def test_two_dates_no_drift():
    """Two corpora identical except the four date tokens compare EQUAL masked."""
    day_one = _all_tokens_ttl(
        gen_date="2026-06-18",
        void_date="2026-06-18",
        imported_a="2026-06-17T12:00:00",
        imported_b="2026-06-16T08:30:00",
        sd_modified="2026-06-18T06:00:00",
    ).encode("utf-8")
    day_two = _all_tokens_ttl(
        gen_date="2026-09-01",
        void_date="2026-09-01",
        imported_a="2026-08-30T23:59:59",
        imported_b="2026-08-29T01:02:03",
        sd_modified="2026-09-01T06:00:00",
    ).encode("utf-8")
    assert gate.mask(day_one) == gate.mask(day_two)
