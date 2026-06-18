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


# ---------------------------------------------------------------------------
# Negative sample + off-vs-on additive-only (the gate must be provable to fail)
# ---------------------------------------------------------------------------

# A minimal flag-off corpus: two subject blocks separated by a blank line.
_FLAG_OFF_MAIN = (
    "<http://aopwiki.org/aop/1>\ta\taopo:AdverseOutcomePathway"
    ' ;\n\tdcterms:title "Pathway one"'
    " .\n"
    "\n"
    "<http://aopwiki.org/event/100>\ta\taopo:KeyEvent"
    ' ;\n\tdcterms:title "Event one hundred"'
    " .\n"
)


def _write_corpus(directory, main_text, *, with_all_files=True, genes_text=""):
    """Write a corpus dir holding the five CORPUS_FILES.

    ``main_text`` is the content of AOPWikiRDF.ttl; ``genes_text`` is the content
    of AOPWikiRDF-Genes.ttl (default empty). The remaining files are written
    empty (the gate masks+compares them too, so they must exist to avoid a
    missing-file hard breach).
    """
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "AOPWikiRDF.ttl"), "w", encoding="utf-8") as fh:
        fh.write(main_text)
    if with_all_files:
        with open(os.path.join(directory, "AOPWikiRDF-Genes.ttl"), "w", encoding="utf-8") as fh:
            fh.write(genes_text)
        for name in (
            "AOPWikiRDF-Enriched.ttl",
            "AOPWikiRDF-Void.ttl",
            "ServiceDescription.ttl",
        ):
            with open(os.path.join(directory, name), "w", encoding="utf-8") as fh:
                fh.write("")
    return directory


def _patch_regen(monkeypatch, off_text, on_text, off_genes="", on_genes=""):
    """Monkeypatch gate.regenerate to write fixture corpora (no pipeline run)."""

    def fake_regenerate(xml_file, out_dir, enable_flags):
        _write_corpus(
            out_dir,
            on_text if enable_flags else off_text,
            genes_text=on_genes if enable_flags else off_genes,
        )
        return out_dir

    monkeypatch.setattr(gate, "regenerate", fake_regenerate)


def test_identical_inputs_pass(tmp_path, monkeypatch):
    """Off == on (additive subset, no drift) -> not breached, main() exits 0."""
    golden_dir = _write_corpus(str(tmp_path / "golden"), _FLAG_OFF_MAIN)
    _patch_regen(monkeypatch, off_text=_FLAG_OFF_MAIN, on_text=_FLAG_OFF_MAIN)

    report = gate.run(
        golden_dir=golden_dir,
        xml_file=str(tmp_path / "snapshot.gz"),
        mode="off-vs-on",
        report_path=str(tmp_path / "r.txt"),
    )
    assert report["breached"] is False

    rc = gate.main([
        "--golden-dir", golden_dir,
        "--xml-file", str(tmp_path / "snapshot.gz"),
        "--mode", "off-vs-on",
        "--report-path", str(tmp_path / "r2.txt"),
    ])
    assert rc == 0


def test_gate_fails_on_injected_diff(tmp_path, monkeypatch):
    """NEGATIVE sample: a mutated subject in the flag-on output breaches.

    Mirrors test_coverage_ratchet.py::test_ratchet_fails_on_drop -- a gate that
    cannot be shown to fail is not validated. The flag-on corpus changes a
    SHARED subject block (event/100), which is NOT additive, so the off-vs-on
    HARD comparison must breach, main() must return 1, and the report must name
    the mutated subject.
    """
    mutated_on = (
        "<http://aopwiki.org/aop/1>\ta\taopo:AdverseOutcomePathway"
        ' ;\n\tdcterms:title "Pathway one"'
        " .\n"
        "\n"
        "<http://aopwiki.org/event/100>\ta\taopo:KeyEvent"
        ' ;\n\tdcterms:title "MUTATED TITLE"'  # shared subject changed
        " .\n"
    )
    golden_dir = _write_corpus(str(tmp_path / "golden"), _FLAG_OFF_MAIN)
    _patch_regen(monkeypatch, off_text=_FLAG_OFF_MAIN, on_text=mutated_on)

    report = gate.run(
        golden_dir=golden_dir,
        xml_file=str(tmp_path / "snapshot.gz"),
        mode="off-vs-on",
        report_path=str(tmp_path / "r.txt"),
    )
    assert report["breached"] is True

    rc = gate.main([
        "--golden-dir", golden_dir,
        "--xml-file", str(tmp_path / "snapshot.gz"),
        "--mode", "off-vs-on",
        "--report-path", str(tmp_path / "r2.txt"),
    ])
    assert rc == 1

    with open(str(tmp_path / "r2.txt"), encoding="utf-8") as fh:
        report_text = fh.read()
    assert "http://aopwiki.org/event/100" in report_text


def test_off_vs_on_delta_is_additive_only(tmp_path, monkeypatch):
    """Flag-on ADDS an rdfs:label to an EXISTING subject -> no breach.

    The flag-on corpus appends an ``rdfs:label "Pathway one"`` predicate to the
    EXISTING aop/1 subject block (the real ``enable_iri_labels=True`` trigger:
    appending the predicate flips aop/1's former-last line terminator from
    ``.`` to ``;`` and adds the label line) and also adds a brand-new
    prov:Activity subject. Both are additive, so the off-vs-on HARD comparison
    must NOT breach. This is the load-bearing case CR-01 fixed -- it FAILS on
    the pre-fix whole-block-equality code. (The mutated-shared-line breach is
    proven separately by test_gate_fails_on_injected_diff.)
    """
    additive_on = (
        "<http://aopwiki.org/aop/1>\ta\taopo:AdverseOutcomePathway"
        ' ;\n\tdcterms:title "Pathway one"'
        ' ;\n\trdfs:label "Pathway one"'  # rdfs:label ADDED to an EXISTING subject
        " .\n"
        "\n"
        "<http://aopwiki.org/event/100>\ta\taopo:KeyEvent"
        ' ;\n\tdcterms:title "Event one hundred"'
        " .\n"
        "\n"
        # NEW flag-gated subject (prov:Activity) -- additive, must not breach.
        "<http://aopwiki.org/activity/1>\ta\tprov:Activity"
        ' ;\n\tprov:wasAssociatedWith <http://example.org/bern2>'
        " .\n"
    )
    golden_dir = _write_corpus(str(tmp_path / "golden"), _FLAG_OFF_MAIN)
    _patch_regen(monkeypatch, off_text=_FLAG_OFF_MAIN, on_text=additive_on)

    report = gate.run(
        golden_dir=golden_dir,
        xml_file=str(tmp_path / "snapshot.gz"),
        mode="off-vs-on",
        report_path=str(tmp_path / "r.txt"),
    )
    assert report["breached"] is False

    rc = gate.main([
        "--golden-dir", golden_dir,
        "--xml-file", str(tmp_path / "snapshot.gz"),
        "--mode", "off-vs-on",
        "--report-path", str(tmp_path / "r2.txt"),
    ])
    assert rc == 0


def test_off_vs_on_prefix_gain_is_additive(tmp_path, monkeypatch):
    """Flag-on AOPWikiRDF-Genes.ttl gains one @prefix preamble line -> no breach.

    Mirrors ``enable_bern2=True`` prepending GENES_PROVENANCE_PREFIX
    (``@prefix : <...> .``) to the Genes file's prefix block. Both off and on
    Genes files have their @prefix declarations as block 0; first_subject()
    returns None for that block so it is excluded from the subject comparison
    (CR-02). The gained @prefix line must therefore NOT breach. This FAILS on
    the pre-fix code, which keyed both prefix blocks on b"@prefix" and reported
    a violation when they differed.
    """
    off_genes = "@prefix a: <http://a/> .\n"
    on_genes = (
        "@prefix : <https://aopwiki.rdf.bigcat-bioinformatics.org/> .\n"
        "@prefix a: <http://a/> .\n"
    )
    golden_dir = _write_corpus(
        str(tmp_path / "golden"), _FLAG_OFF_MAIN, genes_text=off_genes
    )
    _patch_regen(
        monkeypatch,
        off_text=_FLAG_OFF_MAIN,
        on_text=_FLAG_OFF_MAIN,
        off_genes=off_genes,
        on_genes=on_genes,
    )

    report = gate.run(
        golden_dir=golden_dir,
        xml_file=str(tmp_path / "snapshot.gz"),
        mode="off-vs-on",
        report_path=str(tmp_path / "r.txt"),
    )
    assert report["breached"] is False
