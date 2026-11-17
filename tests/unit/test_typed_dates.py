"""Typed creation/modification dates (#143).

With ``typed_dates`` on, the XML timestamps on AOPs, KERs and stressors are
written as xsd:dateTime so SPARQL can sort and compare them as dates. Off, the
output is unchanged.
"""

import importlib.util
import os
import types

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, XSD

from aopwiki_rdf.rdf.writer import _date_literal, write_aop_rdf
from run_conversion import build_config

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AOP1 = URIRef('https://identifiers.org/aop/1')
KER1 = URIRef('https://identifiers.org/aop.relationships/1')
STRESSOR1 = URIRef('https://identifiers.org/aop.stressor/1')


def _entities(aop_modified='2024-01-01T09:30:00'):
    lists = {k: [] for k in (
        'hgnclist', 'ncbigenelist', 'uniprotlist', 'listofcas', 'listofinchikey', 'listofcomptox', 'listofchebi',
        'listofchemspider', 'listofwikidata', 'listofchembl', 'listofpubchem', 'listofdrugbank', 'listofkegg',
        'listoflipidmaps', 'listofhmdb')}
    aop = {
        'dc:identifier': 'aop:1', 'rdfs:label': '"AOP 1"', 'foaf:page': '<https://aopwiki.org/aops/1>',
        'dc:title': '"Test AOP"', 'dcterms:alternative': 'Short', 'dc:source': 'AOPWiki',
        'dcterms:created': '2016-11-29T18:41:50', 'dcterms:modified': aop_modified,
        'aopo:has_key_event': {}, 'aopo:has_key_event_relationship': {'1': {'dc:identifier': 'aop.relationships:1'}},
    }
    ker = {
        'dc:identifier': 'aop.relationships:1', 'rdfs:label': '"KER 1"',
        'foaf:page': '<https://aopwiki.org/relationships/1>',
        'dcterms:created': '2017-02-03T10:00:00', 'dcterms:modified': '2023-05-06T11:12:13',
        'aopo:has_upstream_key_event': {'dc:identifier': 'aop.events:1'},
        'aopo:has_downstream_key_event': {'dc:identifier': 'aop.events:2'},
    }
    stressor = {
        'dc:identifier': 'aop.stressor:1', 'rdfs:label': '"S1"',
        'foaf:page': '<https://identifiers.org/aop.stressor/1>', 'dc:title': '"Cadmium"',
        'dcterms:created': '2018-01-01T00:00:00', 'dcterms:modified': '2022-12-31T23:59:59',
    }
    return {
        'aopdict': {'1': aop}, 'kedict': {}, 'kerdict': {'1': ker}, 'strdict': {'1': stressor},
        'taxdict': {}, 'bioactdict': {}, 'bioobjdict': {}, 'prodict': {}, 'chedict': {}, 'bioprodict': {},
        'symbol_lookup': {}, 'chem_label_by_iri': {}, 'gene_label_by_iri': {}, **lists,
    }


def _write(tmp_path, typed, name='AOPWikiRDF.ttl', **kwargs):
    out = tmp_path / name
    config = None if typed is None else types.SimpleNamespace(
        typed_dates=typed, enable_iri_labels=False, emit_legacy_predicates=False, enable_bern2=False)
    write_aop_rdf(str(out), _entities(**kwargs), os.path.join(PROJECT_ROOT, 'prefixes.csv'), config=config)
    return out


def _graph(path):
    graph = Graph()
    graph.parse(str(path), format='turtle')
    return graph


def test_date_literal_types_iso_timestamps():
    assert _date_literal('2016-11-29T18:41:50', True) == '"2016-11-29T18:41:50"^^xsd:dateTime'


def test_date_literal_is_plain_when_untyped():
    assert _date_literal('2016-11-29T18:41:50', False) == '"2016-11-29T18:41:50"'


def test_date_literal_falls_back_and_records_malformed_values():
    fallbacks = []
    assert _date_literal('2016-11-29', True, fallbacks) == '"2016-11-29"'
    assert _date_literal('29/11/2016 18:41', True, fallbacks) == '"29/11/2016 18:41"'
    assert fallbacks == ['2016-11-29', '29/11/2016 18:41']


def test_typed_dates_on_aops_kers_and_stressors(tmp_path):
    graph = _graph(_write(tmp_path, typed=True))
    expected = {
        (AOP1, DCTERMS.created): '2016-11-29T18:41:50',
        (AOP1, DCTERMS.modified): '2024-01-01T09:30:00',
        (KER1, DCTERMS.created): '2017-02-03T10:00:00',
        (KER1, DCTERMS.modified): '2023-05-06T11:12:13',
        (STRESSOR1, DCTERMS.created): '2018-01-01T00:00:00',
        (STRESSOR1, DCTERMS.modified): '2022-12-31T23:59:59',
    }
    for (subject, predicate), value in expected.items():
        assert list(graph.objects(subject, predicate)) == [Literal(value, datatype=XSD.dateTime)], (subject, predicate)


def test_malformed_date_stays_plain_and_is_logged(tmp_path, caplog):
    graph = _graph(_write(tmp_path, typed=True, aop_modified='2024-01-01'))
    assert list(graph.objects(AOP1, DCTERMS.modified)) == [Literal('2024-01-01')]
    assert list(graph.objects(AOP1, DCTERMS.created)) == [Literal('2016-11-29T18:41:50', datatype=XSD.dateTime)]
    assert '1 created/modified values' in caplog.text


def test_flag_off_output_is_byte_identical_to_no_config(tmp_path):
    off = _write(tmp_path, typed=False, name='off.ttl').read_bytes()
    default = _write(tmp_path, typed=None, name='default.ttl').read_bytes()
    assert off == default
    assert b'^^xsd:dateTime' not in off
    assert b'dcterms:created\t"2016-11-29T18:41:50"' in off


def test_cli_flag():
    assert build_config(['--typed-dates']).typed_dates is True
    assert build_config([]).typed_dates is False


def _load_gate():
    spec = importlib.util.spec_from_file_location('compat_check', os.path.join(PROJECT_ROOT, 'scripts', 'compat_check.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compat_mask_leaves_typed_xml_dates_in_the_main_file_alone():
    gate = _load_gate()
    line = b'\tdcterms:modified\t"2024-01-01T09:30:00"^^xsd:dateTime ;'
    assert gate.mask(line, 'AOPWikiRDF.ttl') == line
    assert b'<MASKED>' in gate.mask(line, 'ServiceDescription.ttl')
