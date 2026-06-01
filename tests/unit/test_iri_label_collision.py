"""Determinism / collision-tiebreak tests for the inverted label maps (D-03).

Two source genes (or chemicals) can map to the SAME xref IRI. Per D-03 the
label-map builders must resolve such collisions to the alphabetically-FIRST
candidate name, and that winner must be independent of dict insertion order
(the byte-stability guarantee). These tests feed identical (iri, candidate)
pairs in two different key orders and assert the resulting maps are equal AND
that the chosen label is the alphabetically-first candidate.
"""

from aopwiki_rdf.mapping.iri_labels import (
    build_chem_label_map,
    build_gene_label_map,
)


def test_gene_collision_alphabetical_first_winner():
    """Two HGNC genes sharing one xref IRI -> alphabetically-first symbol wins."""
    symbol_lookup = {"100": "ZZZ1", "200": "AAA1"}
    # Both genes resolve to the same UniProt IRI -> collision.
    geneiddict = {
        "hgnc:100": ["uniprot:P00001"],
        "hgnc:200": ["uniprot:P00001"],
    }
    m = build_gene_label_map(geneiddict, symbol_lookup)
    # AAA1 < ZZZ1 alphabetically -> AAA1 wins regardless of which gene was seen first.
    assert m["uniprot:P00001"] == "AAA1"


def test_gene_collision_order_independent():
    """Same (iri, symbol) pairs in two key orders -> identical maps."""
    symbol_lookup = {"100": "ZZZ1", "200": "AAA1", "300": "MMM1"}
    forward = {
        "hgnc:100": ["uniprot:P00001", "ncbigene:1"],
        "hgnc:200": ["uniprot:P00001"],
        "hgnc:300": ["ncbigene:1"],
    }
    reverse = {
        "hgnc:300": ["ncbigene:1"],
        "hgnc:200": ["uniprot:P00001"],
        "hgnc:100": ["uniprot:P00001", "ncbigene:1"],
    }
    assert build_gene_label_map(forward, symbol_lookup) == build_gene_label_map(
        reverse, symbol_lookup
    )
    m = build_gene_label_map(forward, symbol_lookup)
    # uniprot collision: AAA1 (200) vs ZZZ1 (100) -> AAA1
    assert m["uniprot:P00001"] == "AAA1"
    # ncbigene collision: MMM1 (300) vs ZZZ1 (100) -> MMM1
    assert m["ncbigene:1"] == "MMM1"


def test_chem_collision_alphabetical_first_winner():
    """Two chemicals sharing one ChEBI IRI -> alphabetically-first name wins."""
    chedict = {
        "chem-1": {"dc:title": '"Zylene"', "cheminf:000407": ["chebi:1234"]},
        "chem-2": {"dc:title": '"Abenzene"', "cheminf:000407": ["chebi:1234"]},
    }
    m = build_chem_label_map(chedict)
    # "Abenzene" < "Zylene" -> Abenzene wins; surrounding quotes stripped.
    assert m["chebi:1234"] == "Abenzene"


def test_chem_collision_order_independent():
    """Same chem (iri, name) pairs in two key orders -> identical maps."""
    forward = {
        "chem-1": {"dc:title": '"Zylene"', "cheminf:000407": ["chebi:1234"]},
        "chem-2": {"dc:title": '"Abenzene"', "cheminf:000407": ["chebi:1234"]},
    }
    reverse = {
        "chem-2": {"dc:title": '"Abenzene"', "cheminf:000407": ["chebi:1234"]},
        "chem-1": {"dc:title": '"Zylene"', "cheminf:000407": ["chebi:1234"]},
    }
    assert build_chem_label_map(forward) == build_chem_label_map(reverse)
    assert build_chem_label_map(forward)["chebi:1234"] == "Abenzene"


def test_chem_covers_cas_inchikey_comptox_singletons():
    """CAS / InChIKey / CompTox single-string xrefs are also labeled."""
    chedict = {
        "chem-1": {
            "dc:title": '"Bisphenol A"',
            "dc:identifier": "cas:80-05-7",
            "cheminf:000059": "inchikey:IISBACLAFKSPIT-UHFFFAOYSA-N",
            "cheminf:000568": "comptox:DTXSID7020182",
        },
    }
    m = build_chem_label_map(chedict)
    assert m["cas:80-05-7"] == "Bisphenol A"
    assert m["inchikey:IISBACLAFKSPIT-UHFFFAOYSA-N"] == "Bisphenol A"
    assert m["comptox:DTXSID7020182"] == "Bisphenol A"
