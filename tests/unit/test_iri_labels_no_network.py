"""No-network guarantee for the label-map builders (LABEL-02 / D-01).

The label maps must be derived ONLY from the already-fetched, in-memory parse /
symbol dicts. They must NOT issue any HTTP request (no BridgeDb, no requests).
These tests monkeypatch ``requests`` so any HTTP call raises, then build both
maps and assert they still produce labels without raising.
"""

import sys

import pytest

from aopwiki_rdf.mapping import iri_labels
from aopwiki_rdf.mapping.iri_labels import (
    build_chem_label_map,
    build_gene_label_map,
)


@pytest.fixture
def explode_on_http(monkeypatch):
    """Make every requests entry-point raise, simulating a hard no-network env."""

    def _boom(*_args, **_kwargs):
        raise AssertionError("network call attempted in label-map build (LABEL-02 violation)")

    requests_mod = sys.modules.get("requests")
    if requests_mod is not None:
        for attr in ("get", "post", "put", "request", "head"):
            monkeypatch.setattr(requests_mod, attr, _boom, raising=False)
        if hasattr(requests_mod, "Session"):
            monkeypatch.setattr(requests_mod.Session, "request", _boom, raising=False)
    yield


def test_gene_map_build_no_network(explode_on_http):
    symbol_lookup = {"1100": "BRCA1", "11998": "TP53"}
    geneiddict = {
        "hgnc:1100": ["ncbigene:672", "uniprot:P38398"],
        "hgnc:11998": ["ncbigene:7157"],
    }
    m = build_gene_label_map(geneiddict, symbol_lookup)
    assert m["ncbigene:672"] == "BRCA1"
    assert m["uniprot:P38398"] == "BRCA1"
    assert m["ncbigene:7157"] == "TP53"


def test_gene_map_skips_symbol_less_gene(explode_on_http):
    """A gene whose numeric HGNC id is absent from symbol_lookup contributes
    NO entry to the label map -- its xref IRIs stay unlabeled rather than being
    given the all-digit HGNC id as a pseudo-label (D-02, WR-02)."""
    symbol_lookup = {"1100": "BRCA1"}  # 11998 deliberately absent
    geneiddict = {
        "hgnc:1100": ["ncbigene:672"],
        "hgnc:11998": ["ncbigene:7157", "uniprot:P04637"],
    }
    m = build_gene_label_map(geneiddict, symbol_lookup)
    assert m["ncbigene:672"] == "BRCA1"
    # The symbol-less gene's xref IRIs are absent (not labeled with "11998").
    assert "ncbigene:7157" not in m
    assert "uniprot:P04637" not in m
    assert "11998" not in m.values()


def test_chem_map_build_no_network(explode_on_http):
    chedict = {
        "chem-1": {
            "dc:title": '"Bisphenol A"',
            "dc:identifier": "cas:80-05-7",
            "cheminf:000407": ["chebi:1234"],
        },
    }
    m = build_chem_label_map(chedict)
    assert m["chebi:1234"] == "Bisphenol A"
    assert m["cas:80-05-7"] == "Bisphenol A"


def test_module_does_not_import_requests_at_top_level():
    """The label-map module must not pull in the HTTP stack to build maps.

    Parses the module AST and asserts neither ``requests`` nor the BridgeDb
    mapper is imported (prose mentions of these names in docstrings are fine --
    we forbid the *import*, which is what would enable a network call).
    """
    import ast

    with open(iri_labels.__file__, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)

    assert "requests" not in imported_modules
    assert not any("bridgedb" in m.lower() for m in imported_modules)
