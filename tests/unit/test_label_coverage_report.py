"""Coverage-report tests for report_label_coverage (D-02 / D-07).

The report must:
  * return a per-source labeled/unlabeled count dict plus a SORTED list of the
    opaque (unlabeled) IRIs -- the honest record (D-02): an IRI with no label is
    recorded, never silently dropped;
  * write that dict as a JSON artifact whose re-parsed content equals the
    returned dict (D-07: the artifact the BERN2 probe never wrote);
  * be byte-stable / deterministic for the same inputs.
"""

import json
import os

from aopwiki_rdf.mapping.iri_labels import report_label_coverage


def test_per_source_counts_and_sorted_unlabeled(tmp_path):
    listofchebi = ["chebi:1", "chebi:2", "chebi:3"]
    listofcas = ["cas:80-05-7", "cas:50-00-0"]
    listofuniprot = ["uniprot:P04637"]
    label_map = {
        "chebi:1": "Foo",
        "chebi:2": "Bar",
        # chebi:3 deliberately unlabeled (opaque)
        "cas:80-05-7": "Bisphenol A",
        # cas:50-00-0 deliberately unlabeled
        # uniprot:P04637 deliberately unlabeled
    }
    report_path = os.path.join(tmp_path, "label-coverage-report.json")

    result = report_label_coverage(
        [listofchebi, listofcas, listofuniprot], label_map, report_path=report_path
    )

    assert result["per_source"]["ChEBI"] == {"labeled": 2, "unlabeled": 1}
    assert result["per_source"]["CAS"] == {"labeled": 1, "unlabeled": 1}
    assert result["per_source"]["UniProt"] == {"labeled": 0, "unlabeled": 1}

    # Honest record (D-02): every unlabeled IRI is present and the list is sorted.
    assert result["unlabeled_iris"] == sorted(
        ["chebi:3", "cas:50-00-0", "uniprot:P04637"]
    )


def test_opaque_iri_not_silently_dropped(tmp_path):
    """An IRI absent from the label map MUST appear in unlabeled_iris."""
    report_path = os.path.join(tmp_path, "r.json")
    result = report_label_coverage(
        [["chebi:999"]], label_map_combined={}, report_path=report_path
    )
    assert "chebi:999" in result["unlabeled_iris"]
    assert result["per_source"]["ChEBI"]["unlabeled"] == 1


def test_json_artifact_written_and_reparses_equal(tmp_path):
    report_path = os.path.join(tmp_path, "label-coverage-report.json")
    result = report_label_coverage(
        [["chebi:1", "chebi:2"]],
        {"chebi:1": "Foo"},
        report_path=report_path,
    )
    assert os.path.exists(report_path)
    with open(report_path, encoding="utf-8") as fh:
        reparsed = json.load(fh)
    assert reparsed == result


def test_deterministic_for_same_inputs(tmp_path):
    iris = [["chebi:2", "chebi:1"], ["cas:1"]]
    lm = {"chebi:1": "A"}
    p1 = os.path.join(tmp_path, "a.json")
    p2 = os.path.join(tmp_path, "b.json")
    r1 = report_label_coverage(iris, lm, report_path=p1)
    r2 = report_label_coverage(iris, lm, report_path=p2)
    assert r1 == r2
    assert open(p1, encoding="utf-8").read() == open(p2, encoding="utf-8").read()


def test_accepts_flat_iterable(tmp_path):
    """A flat iterable of IRIs (not list-of-lists) is also accepted."""
    p = os.path.join(tmp_path, "r.json")
    result = report_label_coverage(
        ["chebi:1", "cas:1"], {"chebi:1": "Foo"}, report_path=p
    )
    assert result["per_source"]["ChEBI"]["labeled"] == 1
    assert result["per_source"]["CAS"]["unlabeled"] == 1
