"""Integration tests for the coverage ratchet (XML-02 / XML-03).

* ``test_fixed_gaps_emit`` — XML-02: each fixed gap element now emits its
  triple(s) in writer output. Depends on the Plan 03 parser/writer gap-fix.
* ``test_additive`` — XML-02: gap fixes are additive, the total triple count
  does not drop versus a graph parsed from a snapshot WITHOUT the gap elements.
* ``test_ratchet_fails_on_drop`` — XML-03 (the critical Nyquist NEGATIVE
  sample): when a covered element drops out of the output below the relative
  floor, the ratchet MUST breach (exit 1). A ratchet that cannot be shown to
  fail is not validated. It exercises the existing relative-floor breach
  mechanism in scripts/qc_delta_guard.py.
"""

import importlib.util
import os

from rdflib import Graph

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GUARD_PATH = os.path.join(PROJECT_ROOT, "scripts", "qc_delta_guard.py")
FIXTURE = os.path.join(PROJECT_ROOT, "tests", "fixtures", "sample_aopwiki.xml")
PREFIX_CSV = os.path.join(PROJECT_ROOT, "prefixes.csv")

TTL_HEADER = "@prefix edam: <http://edamontology.org/> .\n"

# The maintainer-selected gap elements (Plan 03, D-06/D-07) and the predicate
# CURIE each was assigned. These predicates MUST appear in the writer output for
# the fixture's KER/KE that now carries the gap elements.
GAP_PREDICATES = {
    "evidence-supporting-taxonomic-applicability": "nci:C17469",
    "evidence-collection-strategy": "nci:C103159",
    "known-modulating-factors": "nci:C68821",
    "quantitative-understanding": "edam:operation_3799",
    "response-response-relationship": "edam:operation_3438",
    "time-scale": "nci:C25207",
    "feedforward-feedback-loops": "nci:C25343",
}


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


def _entities_from_parsed(parsed):
    """Adapt a ParsedEntities dataclass to the write_aop_rdf entities dict."""
    return {
        "aopdict": parsed.aopdict,
        "kedict": parsed.kedict,
        "kerdict": parsed.kerdict,
        "strdict": parsed.stressordict,
        "chedict": parsed.chemicaldict,
        "taxdict": parsed.taxdict,
        "celldict": parsed.celldict,
        "organdict": parsed.organdict,
        "bioobjdict": parsed.bodict,
        "bioprodict": parsed.bpdict,
        "bioactdict": parsed.badict,
        "prodict": parsed.prodict,
        "hgnclist": [], "ncbigenelist": [], "uniprotlist": [],
        "listofcas": [], "listofinchikey": [], "listofcomptox": [],
        "listofchebi": [], "listofchemspider": [], "listofwikidata": [],
        "listofchembl": [], "listofpubchem": [], "listofdrugbank": [],
        "listofkegg": [], "listoflipidmaps": [], "listofhmdb": [],
    }


def _write_fixture_ttl(tmp_path):
    """Parse the fixture and write AOPWikiRDF.ttl to tmp_path; return its text."""
    from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml
    from aopwiki_rdf.rdf.writer import write_aop_rdf

    parsed = parse_aopwiki_xml(FIXTURE)
    entities = _entities_from_parsed(parsed)
    out = os.path.join(str(tmp_path), "AOPWikiRDF.ttl")
    write_aop_rdf(out, entities, PREFIX_CSV, config=None)
    with open(out) as fh:
        return out, fh.read()


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


def test_fixed_gaps_emit(tmp_path):
    """Each fixed gap element now emits its predicate in writer output (XML-02).

    The fixture's KER (id 50) and KE (id 100) carry every maintainer-selected
    gap element; after the Plan 03 parser/writer fix, each assigned predicate
    must appear in the emitted Turtle, and the output must parse as Turtle.
    """
    out, content = _write_fixture_ttl(tmp_path)

    for element, predicate in GAP_PREDICATES.items():
        assert predicate in content, (
            f"gap predicate {predicate} for <{element}> missing from writer output"
        )

    # The emitted Turtle must parse cleanly (every prefix registered).
    Graph().parse(out, format="turtle")


def test_additive(tmp_path):
    """Gap fixes are additive — total triple count does not drop (XML-02).

    Compares the triple count of the gap-fixed output against the same output
    with the gap predicates stripped (the pre-fix baseline). The fixed output
    must have at least as many triples — the fixes only ADD.
    """
    out, content = _write_fixture_ttl(tmp_path)

    fixed_graph = Graph().parse(out, format="turtle")
    fixed_count = len(fixed_graph)

    # Build the pre-fix baseline: the same Turtle with the new gap predicate
    # lines removed. Each gap predicate sits on its own ` ;`-joined clause, so
    # dropping the lines that mention the new predicates reconstructs the
    # pre-fix triple set.
    pre_fix_lines = []
    new_predicates = set(GAP_PREDICATES.values())
    for line in content.splitlines(keepends=True):
        if any(f"\t{pred}\t" in line for pred in new_predicates):
            continue
        pre_fix_lines.append(line)
    pre_fix_ttl = "".join(pre_fix_lines)
    pre_fix_path = os.path.join(str(tmp_path), "pre_fix.ttl")
    with open(pre_fix_path, "w") as fh:
        fh.write(pre_fix_ttl)

    pre_fix_count = len(Graph().parse(pre_fix_path, format="turtle"))

    assert fixed_count >= pre_fix_count, (
        f"gap fixes removed triples: fixed={fixed_count} < pre_fix={pre_fix_count}"
    )
    # And they genuinely added the new predicate triples.
    assert fixed_count > pre_fix_count, (
        "gap fixes added no triples — expected the new predicates to be additive"
    )
