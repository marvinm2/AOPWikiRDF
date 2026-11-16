"""Labels, comments and class typing for the terms the main file uses.

Opaque ontology predicates (nci:C25664, edam:data_2042, ...) need a label and
comment in the endpoint so that people and LLM-based query tools can tell what
they hold. All of it is gated on ``enable_iri_labels`` like the existing
predicate labels, so flag-off output is unchanged.
"""

import os
import shutil
import types

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NCI = Namespace('http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#')
EDAM = Namespace('http://edamontology.org/')
AOPO = Namespace('http://aopkb.org/aop_ontology#')
GO_ROOT = URIRef('http://purl.obolibrary.org/obo/GO_0008150')


def _entities(with_go_component=False):
    bioprodict = {}
    if with_go_component:
        bioprodict = {'p1': {'dc:identifier': 'go:0008150', 'dc:title': '"biological_process"', 'dc:source': '"GO"'}}
    empty = {k: [] for k in (
        'hgnclist', 'ncbigenelist', 'uniprotlist', 'listofcas', 'listofinchikey', 'listofcomptox', 'listofchebi',
        'listofchemspider', 'listofwikidata', 'listofchembl', 'listofpubchem', 'listofdrugbank', 'listofkegg',
        'listoflipidmaps', 'listofhmdb')}
    return {
        'aopdict': {}, 'kedict': {}, 'kerdict': {}, 'strdict': {}, 'taxdict': {}, 'bioactdict': {},
        'bioobjdict': {}, 'prodict': {}, 'chedict': {}, 'bioprodict': bioprodict, 'symbol_lookup': {},
        'chem_label_by_iri': {}, 'gene_label_by_iri': {}, **empty,
    }


def _write(tmp_path, labels_on, **entity_kwargs):
    from aopwiki_rdf.rdf.writer import write_aop_rdf

    shutil.copy(os.path.join(PROJECT_ROOT, 'data', 'typelabels.txt'), tmp_path / 'typelabels.txt')
    out = tmp_path / 'AOPWikiRDF.ttl'
    config = types.SimpleNamespace(enable_iri_labels=labels_on, emit_legacy_predicates=False, enable_bern2=False)
    write_aop_rdf(str(out), _entities(**entity_kwargs), os.path.join(PROJECT_ROOT, 'prefixes.csv'), config=config)
    graph = Graph()
    graph.parse(str(out), format='turtle')
    return graph


def _labels(graph, term):
    return [str(o) for o in graph.objects(term, RDFS.label)]


def test_quantitative_understanding_label_replaces_gene_annotation(tmp_path):
    graph = _write(tmp_path, labels_on=True)
    assert _labels(graph, EDAM.operation_3799) == ['quantitative understanding']


@pytest.mark.parametrize(
    ('term', 'label'),
    [
        (NCI.C25664, 'level of biological organisation'),
        (NCI.C80263, 'biological plausibility'),
        (EDAM.data_2042, 'empirical support'),
        (NCI.C71478, 'uncertainties and inconsistencies'),
        (AOPO.AopContext, 'domain of applicability'),
    ],
)
def test_opaque_predicates_get_one_usage_label(tmp_path, term, label):
    assert _labels(_write(tmp_path, labels_on=True), term) == [label]


def test_dual_use_terms_keep_their_single_class_label_and_gain_a_comment(tmp_path):
    graph = _write(tmp_path, labels_on=True)
    assert _labels(graph, NCI.C54571) == ['Stressor']
    assert any('predicate' in str(c) for c in graph.objects(NCI.C54571, RDFS.comment))


def test_go_root_is_not_labelled_twice_when_it_is_a_component(tmp_path):
    graph = _write(tmp_path, labels_on=True, with_go_component=True)
    assert _labels(graph, GO_ROOT) == ['biological_process']


def test_go_root_gets_the_usage_label_when_no_component_labels_it(tmp_path):
    assert _labels(_write(tmp_path, labels_on=True), GO_ROOT) == ['biological process']


def test_classes_are_typed_owl_class_with_comments(tmp_path):
    graph = _write(tmp_path, labels_on=True)
    for cls in (AOPO.AdverseOutcomePathway, AOPO.KeyEvent, AOPO.KeyEventRelationship, NCI.C54571, GO_ROOT):
        assert (cls, RDF.type, OWL.Class) in graph, cls
        assert list(graph.objects(cls, RDFS.comment)), cls


def test_void_terms_and_the_stale_go_iri_are_not_typed_as_classes(tmp_path):
    graph = _write(tmp_path, labels_on=True)
    for term in ('http://rdfs.org/ns/void#Dataset', 'http://purl.org/obo/owl/GO#0008150'):
        assert (URIRef(term), RDF.type, OWL.Class) not in graph


def test_typelabels_description_is_copied_to_a_comment(tmp_path):
    graph = _write(tmp_path, labels_on=True)
    comments = [str(c) for c in graph.objects(EDAM.data_1027, RDFS.comment)]
    assert comments == ['An NCBI unique identifier of a gene.']


def test_no_term_gets_more_than_one_label(tmp_path):
    graph = _write(tmp_path, labels_on=True, with_go_component=True)
    counts = {}
    for subject, _, _ in graph.triples((None, RDFS.label, None)):
        counts[subject] = counts.get(subject, 0) + 1
    assert {s: n for s, n in counts.items() if n > 1} == {}


def test_flag_off_emits_no_comments_or_class_typing(tmp_path):
    graph = _write(tmp_path, labels_on=False)
    assert not list(graph.triples((None, RDFS.comment, None)))
    assert not list(graph.triples((None, RDF.type, OWL.Class)))
    assert _labels(graph, NCI.C25664) == []
